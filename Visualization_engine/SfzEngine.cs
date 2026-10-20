namespace SynthesiaClone;

/// <summary>
/// Plays a <see cref="PlaybackSession"/> on an SFZ piano (Salamander), with the same schedule,
/// transport and sample-accurate onsets as <see cref="SoundFontEngine"/>.
/// </summary>
/// <remarks>
/// Covers the opcodes <see cref="SfzInstrument"/> reads: velocity layers, cubic resampling, an
/// exponential release, the sustain pedal, release-triggered regions with <c>rt_decay</c>,
/// pedal-noise regions and <c>group</c>/<c>off_by</c>. Phase 4a measured it on Salamander: 100% of
/// the opcodes the instrument uses, no late block over ten minutes of the densest library song at
/// 1.0x and 2.0x, and deterministic renders.
///
/// Transport changes are silent: a pause, seek or resume moves the pedal and the dampers without the
/// pedal and release noises, which only the score's own events play.
///
/// Not thread-safe. The live engine is wrapped in <see cref="LockedPianoEngine"/>; an exporter builds
/// its own and shares only the read-only <see cref="SfzPiano"/>.
/// </remarks>
public sealed unsafe class SfzEngine : IPianoEngine
{
    public const int MaximumPolyphony = 256;

    /// <summary>
    /// Matches the loudness of the SoundFont piano: the Phase 4a renders the user picked were scaled
    /// to the YDP renders' loudness, which put this gain between 0.34 and 0.42 on the three songs.
    /// </summary>
    public const float MasterGain = 0.37f;

    /// <summary>A voice cut by off_by or a seek fades over this, rather than clicking.</summary>
    private const double FastReleaseSeconds = 0.01;
    private const float Silent = 1e-4f;
    private const int SustainThreshold = 64;

    private readonly SfzPiano piano;
    private readonly IAudioSink sink;
    private readonly PlaybackSession session;
    private readonly PlaybackEvent[] events;
    private readonly bool hasPedal;
    private readonly int sampleRate;
    private readonly Voice[] voices = new Voice[MaximumPolyphony];
    private readonly Prepared[] regions;
    private readonly float fastRelease;
    private readonly Freeverb reverb;
    // Seeded, so an export is the same file every time.
    private readonly Random random = new(20261019);

    // Allocated once. The render path must not allocate.
    private readonly float[] left;
    private readonly float[] right;
    private readonly float[] interleaved;

    private readonly double[] noteOnTime = new double[128];
    private readonly int[] noteOnVelocity = new int[128];
    private readonly bool[] keyDown = new bool[128];
    private readonly bool[] pendingRelease = new bool[128];

    private int cursor;
    private double blockStartSong;
    private double renderedSeconds;
    private double eventSeconds;
    private double rate = 1.0;
    private double stagedRate = 1.0;
    private bool running;
    private bool filled;
    private int pedal;

    public SfzEngine(SfzPiano piano, IAudioSink sink, PlaybackSession session, int sampleRate)
    {
        this.piano = piano ?? throw new ArgumentNullException(nameof(piano));
        this.session = session ?? throw new ArgumentNullException(nameof(session));
        this.sink = sink ?? throw new ArgumentNullException(nameof(sink));
        this.sampleRate = sampleRate > 0
            ? sampleRate
            : throw new ArgumentOutOfRangeException(nameof(sampleRate), sampleRate, "Sample rate must be positive.");
        events = session.Events;
        hasPedal = session.Pedal.Count > 0;
        for (int index = 0; index < voices.Length; index++)
        {
            voices[index] = new Voice();
        }
        regions = piano.Instrument.Regions.Select(region =>
        {
            BankSample sample = piano.Bank[region.Sample];
            return new Prepared(region, sample.Offset, sample.Frames, sample.Start, (double)sample.SampleRate / sampleRate,
                (float)Math.Pow(10, region.VolumeDb / 20), Decay(Math.Max(region.AmpegRelease, 0.001)));
        }).ToArray();
        fastRelease = Decay(FastReleaseSeconds);
        left = new float[sink.BlockFrames];
        right = new float[sink.BlockFrames];
        interleaved = new float[sink.BlockFrames * 2];
        reverb = new Freeverb(sampleRate);
    }

    public double SubmittedSongSeconds => blockStartSong;
    public int UnderrunCount { get; private set; }
    public bool IsRunning => running;
    public int StolenVoices { get; private set; }

    public int ActiveVoiceCount
    {
        get
        {
            int count = 0;
            foreach (Voice voice in voices)
            {
                count += voice.Active ? 1 : 0;
            }
            return count;
        }
    }

    public void Start()
    {
        running = true;
        // A pause lifted the pedal; put it back where the score has it at this point.
        if (hasPedal)
        {
            SetPedal(session.PedalBefore(cursor), noises: false);
        }
    }

    public void Stop()
    {
        running = false;
        // The pedal comes up first, or every voice it holds would ring on through the pause.
        if (hasPedal)
        {
            SetPedal(0, noises: false);
        }
        // Release rather than cut: the strings and the reverb keep decaying, as a piano does.
        for (int key = 0; key < 128; key++)
        {
            if (keyDown[key] || pendingRelease[key])
            {
                keyDown[key] = false;
                ReleaseKey(key, noises: false);
            }
        }
    }

    public void SetRate(double value) => stagedRate = value;

    public void Seek(double songSeconds)
    {
        foreach (Voice voice in voices)
        {
            if (voice.Active)
            {
                voice.Release(fastRelease);
            }
        }
        Array.Clear(keyDown);
        Array.Clear(pendingRelease);
        pedal = 0;
        blockStartSong = Math.Max(0, songSeconds);
        cursor = UpperBound(blockStartSong);
        if (hasPedal)
        {
            SetPedal(session.PedalBefore(cursor), noises: false);
        }

        // Notes that started before this point and have not ended sound again from their attack,
        // as on the SoundFont piano, so seeking into a held chord does not land in silence.
        Span<int> depth = stackalloc int[88];
        Span<int> velocity = stackalloc int[88];
        for (int index = 0; index < cursor; index++)
        {
            PlaybackEvent item = events[index];
            if (item.IsPedal)
            {
                continue;
            }
            if (item.IsNoteOn)
            {
                depth[item.KeyIndex]++;
                velocity[item.KeyIndex] = item.Velocity;
            }
            else if (depth[item.KeyIndex] > 0)
            {
                depth[item.KeyIndex]--;
            }
        }
        eventSeconds = renderedSeconds;
        for (int keyIndex = 0; keyIndex < depth.Length; keyIndex++)
        {
            if (depth[keyIndex] > 0)
            {
                NoteOn(keyIndex + 21, velocity[keyIndex]);
            }
        }
    }

    public void Pump()
    {
        // As in SoundFontEngine: two blocks in one pass means both sub-buffers were free on entry,
        // so the stream had already run dry - except on the first fill.
        int rendered = 0;
        while (sink.WantsBlock)
        {
            RenderBlock();
            rendered++;
        }
        if (rendered > 1 && filled)
        {
            UnderrunCount++;
        }
        filled |= rendered > 0;
    }

    public void RenderBlock()
    {
        int frames = sink.BlockFrames;
        rate = stagedRate;
        // Paused: render anyway so tails and reverb decay, without advancing song time.
        double songPerFrame = running ? rate / sampleRate : 0.0;
        Array.Clear(left);
        Array.Clear(right);

        int position = 0;
        while (position < frames)
        {
            int next = frames;
            if (songPerFrame > 0 && cursor < events.Length)
            {
                double delta = events[cursor].Time - (blockStartSong + (position * songPerFrame));
                int relative = delta <= 0 ? 0 : (int)Math.Ceiling(delta / songPerFrame);
                if (position + relative < frames)
                {
                    next = position + relative;
                }
            }

            if (next > position)
            {
                Mix(position, next - position);
                position = next;
            }

            if (songPerFrame <= 0)
            {
                break;
            }

            double timeHere = blockStartSong + (position * songPerFrame);
            eventSeconds = renderedSeconds + (double)position / sampleRate;
            while (cursor < events.Length && events[cursor].Time <= timeHere)
            {
                Apply(events[cursor]);
                cursor++;
            }

            if (next == frames)
            {
                break;
            }
        }

        blockStartSong += frames * songPerFrame;
        renderedSeconds += (double)frames / sampleRate;
        reverb.Process(left, right);
        for (int frame = 0; frame < frames; frame++)
        {
            interleaved[frame * 2] = left[frame] * MasterGain;
            interleaved[(frame * 2) + 1] = right[frame] * MasterGain;
        }
        sink.Submit(interleaved);
    }

    private void Apply(PlaybackEvent item)
    {
        if (item.IsPedal)
        {
            SetPedal(item.Velocity, noises: true);
        }
        else if (item.IsNoteOn)
        {
            NoteOn(item.KeyIndex + 21, item.Velocity);
        }
        else
        {
            NoteOff(item.KeyIndex + 21);
        }
    }

    private void NoteOn(int key, int velocity)
    {
        keyDown[key] = true;
        pendingRelease[key] = false;
        noteOnTime[key] = eventSeconds;
        noteOnVelocity[key] = velocity;
        double roll = random.NextDouble();
        foreach (Prepared prepared in regions)
        {
            SfzRegion region = prepared.Region;
            if (!region.ReleaseTrigger && !region.PedalTriggered && key >= region.LoKey && key <= region.HiKey &&
                velocity >= region.LoVel && velocity <= region.HiVel && roll >= region.LoRand && roll < region.HiRand)
            {
                Begin(prepared, key, velocity, 1f);
            }
        }
    }

    private void NoteOff(int key)
    {
        keyDown[key] = false;
        if (pedal >= SustainThreshold)
        {
            pendingRelease[key] = true;
            return;
        }
        ReleaseKey(key, noises: true);
    }

    /// <summary>The damper falls: the key's voices release, and with <paramref name="noises"/> its release samples sound.</summary>
    private void ReleaseKey(int key, bool noises)
    {
        pendingRelease[key] = false;
        foreach (Voice voice in voices)
        {
            if (voice.Active && voice.Key == key && !voice.Releasing && !voice.Prepared.Region.ReleaseTrigger)
            {
                voice.Release(voice.Prepared.ReleaseCoefficient);
            }
        }
        if (!noises)
        {
            return;
        }
        int velocity = noteOnVelocity[key];
        double held = eventSeconds - noteOnTime[key];
        double roll = random.NextDouble();
        foreach (Prepared prepared in regions)
        {
            SfzRegion region = prepared.Region;
            if (region.ReleaseTrigger && key >= region.LoKey && key <= region.HiKey && velocity >= region.LoVel &&
                velocity <= region.HiVel && roll >= region.LoRand && roll < region.HiRand)
            {
                Begin(prepared, key, velocity, (float)Math.Pow(10, -region.RtDecay * held / 20));
            }
        }
    }

    private void SetPedal(int value, bool noises)
    {
        int previous = pedal;
        pedal = value;
        if (noises)
        {
            double roll = random.NextDouble();
            foreach (Prepared prepared in regions)
            {
                SfzRegion region = prepared.Region;
                bool inside = value >= region.OnLoCc64 && value <= region.OnHiCc64;
                bool wasInside = previous >= region.OnLoCc64 && previous <= region.OnHiCc64;
                if (region.PedalTriggered && inside && !wasInside && roll >= region.LoRand && roll < region.HiRand)
                {
                    Begin(prepared, -1, 127, 1f);
                }
            }
        }
        if (previous >= SustainThreshold && value < SustainThreshold)
        {
            for (int key = 0; key < 128; key++)
            {
                if (pendingRelease[key] && !keyDown[key])
                {
                    ReleaseKey(key, noises);
                }
            }
        }
    }

    private void Begin(Prepared prepared, int key, int velocity, float extraGain)
    {
        SfzRegion region = prepared.Region;
        if (region.Group != 0)
        {
            foreach (Voice other in voices)
            {
                if (other.Active && other.Prepared.Region.OffBy == region.Group)
                {
                    other.Release(fastRelease);
                }
            }
        }
        double normalized = velocity / 127.0;
        double track = Math.Abs(region.AmpVeltrack) / 100.0;
        float velocityGain = (float)((1 - track) + (track * normalized * normalized));
        double semitones = key < 0 ? 0 : (key - region.PitchKeycenter) * region.PitchKeytrack / 100.0;
        double step = prepared.RateRatio * Math.Pow(2, (semitones + (region.Tune / 100.0)) / 12.0);
        Allocate().Begin(prepared, key, step, prepared.VolumeGain * velocityGain * extraGain);
    }

    /// <summary>A free voice, or else the quietest one, released voices counting half.</summary>
    private Voice Allocate()
    {
        Voice? quietest = null;
        foreach (Voice voice in voices)
        {
            if (!voice.Active)
            {
                return voice;
            }
            if (quietest is null || voice.Loudness < quietest.Loudness)
            {
                quietest = voice;
            }
        }
        StolenVoices++;
        return quietest!;
    }

    private void Mix(int start, int count)
    {
        short* data = piano.Bank.Frames;
        foreach (Voice voice in voices)
        {
            if (!voice.Active)
            {
                continue;
            }
            Prepared prepared = voice.Prepared;
            long origin = prepared.Offset;
            int last = prepared.Frames - 3;
            double position = voice.Position;
            float envelope = voice.Envelope;
            float coefficient = voice.Coefficient;
            float gain = voice.Gain * (1f / 32768f);
            for (int frame = start; frame < start + count; frame++)
            {
                int index = (int)position;
                if (index >= last || envelope < Silent)
                {
                    voice.Active = false;
                    break;
                }
                float t = (float)(position - index);
                short* here = data + ((origin + index) * 2);
                short* before = index > 0 ? here - 2 : here;
                left[frame] += Hermite(before[0], here[0], here[2], here[4], t) * gain * envelope;
                right[frame] += Hermite(before[1], here[1], here[3], here[5], t) * gain * envelope;
                position += voice.Step;
                envelope *= coefficient;
            }
            voice.Position = position;
            voice.Envelope = envelope;
        }
    }

    private static float Hermite(float before, float here, float after, float next, float t)
    {
        float c1 = 0.5f * (after - before);
        float c2 = before - (2.5f * here) + (2f * after) - (0.5f * next);
        float c3 = (0.5f * (next - before)) + (1.5f * (here - after));
        return (((((c3 * t) + c2) * t) + c1) * t) + here;
    }

    /// <summary>Per-sample decay that falls 60 dB over <paramref name="seconds"/>.</summary>
    private float Decay(double seconds) => (float)Math.Exp(Math.Log(1e-3) / (seconds * sampleRate));

    private int UpperBound(double time)
    {
        int low = 0;
        int high = events.Length;
        while (low < high)
        {
            int middle = low + ((high - low) / 2);
            if (events[middle].Time <= time)
            {
                low = middle + 1;
            }
            else
            {
                high = middle;
            }
        }
        return low;
    }

    private sealed record Prepared(SfzRegion Region, long Offset, int Frames, int Start, double RateRatio, float VolumeGain,
        float ReleaseCoefficient);

    private sealed class Voice
    {
        public bool Active;
        public Prepared Prepared = null!;
        public int Key;
        public double Position;
        public double Step;
        public float Gain;
        public float Envelope;
        public float Coefficient;
        public bool Releasing;

        public float Loudness => Releasing ? Gain * Envelope * 0.5f : Gain * Envelope;

        public void Begin(Prepared prepared, int key, double step, float gain)
        {
            Active = true;
            Prepared = prepared;
            Key = key;
            Position = prepared.Start;
            Step = step;
            Gain = gain;
            Envelope = 1f;
            // Sounding until released, except a one-shot noise, which plays its sample out.
            Coefficient = 1f;
            Releasing = false;
        }

        public void Release(float coefficient)
        {
            Releasing = true;
            Coefficient = Math.Min(Coefficient, coefficient);
        }
    }
}
