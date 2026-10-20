using SynthesiaClone;

namespace SfzSpike;

/// <summary>A note on, note off or pedal change at a song time, ordered as the app orders them.</summary>
public readonly record struct SpikeEvent(double Time, int Rank, int Key, int Value)
{
    public const int PedalUp = 0, NoteOff = 1, NoteOn = 2, PedalDown = 3;

    /// <summary>The same events, in the same order, that <see cref="PlaybackSession"/> plays.</summary>
    public static SpikeEvent[] From(PlaybackSession session) => session.Notes
        .SelectMany(note => new[]
        {
            new SpikeEvent(note.StartTime, NoteOn, note.MidiPitch, note.Velocity),
            new SpikeEvent(note.EndTime, NoteOff, note.MidiPitch, 0)
        })
        .Concat(session.Pedal.Select(change => new SpikeEvent(change.Time, change.IsDown ? PedalDown : PedalUp, -1, change.Value)))
        .OrderBy(item => item.Time).ThenBy(item => item.Rank).ThenBy(item => item.Key)
        .ToArray();
}

/// <summary>
/// A managed SFZ player for the subset <see cref="SfzInstrument"/> reads: velocity layers, cubic
/// resampling, an exponential release, the sustain pedal, release-triggered regions with
/// <c>rt_decay</c>, pedal-triggered regions, and <c>group</c>/<c>off_by</c>. Events land on their own
/// sample, as in the app's SoundFont engine.
/// </summary>
public sealed unsafe class SfzSynth
{
    public const int MaximumPolyphony = 256;

    /// <summary>A voice cut by off_by or stolen fades over this, rather than clicking.</summary>
    private const double FastReleaseSeconds = 0.01;
    private const float Silent = 1e-4f;

    private readonly SfzInstrument instrument;
    private readonly SfzBank bank;
    private readonly IAudioSink sink;
    private readonly SpikeEvent[] events;
    private readonly int sampleRate;
    private readonly Voice[] voices = new Voice[MaximumPolyphony];
    private readonly Prepared[] regions;
    private readonly float[] left;
    private readonly float[] right;
    private readonly float[] interleaved;
    private readonly Freeverb? reverb;
    private readonly Random random = new(20261019);

    private readonly double[] noteOnTime = new double[128];
    private readonly int[] noteOnVelocity = new int[128];
    private readonly bool[] keyDown = new bool[128];
    private readonly bool[] pendingRelease = new bool[128];

    private int cursor;
    private double blockStartSong;
    private double renderedSeconds;
    private int pedal;

    public SfzSynth(SfzInstrument instrument, SfzBank bank, IAudioSink sink, PlaybackSession session, int sampleRate,
        bool reverb, float masterGain)
    {
        this.instrument = instrument;
        this.bank = bank;
        this.sink = sink;
        this.sampleRate = sampleRate;
        MasterGain = masterGain;
        events = SpikeEvent.From(session);
        for (int index = 0; index < voices.Length; index++)
        {
            voices[index] = new Voice();
        }
        regions = instrument.Regions.Select(region =>
        {
            BankSample sample = bank[region.Sample];
            return new Prepared(region, sample.Offset, sample.Frames, sample.Start, (double)sample.SampleRate / sampleRate,
                (float)Math.Pow(10, region.VolumeDb / 20), (float)Math.Exp(Math.Log(1e-3) / (Math.Max(region.AmpegRelease, 0.001) * sampleRate)));
        }).ToArray();
        left = new float[sink.BlockFrames];
        right = new float[sink.BlockFrames];
        interleaved = new float[sink.BlockFrames * 2];
        this.reverb = reverb ? new Freeverb(sampleRate) : null;
    }

    public float MasterGain { get; }
    public double Rate { get; set; } = 1.0;
    public double SubmittedSongSeconds => blockStartSong;
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
    public int PeakVoices { get; private set; }
    public int StolenVoices { get; private set; }

    public void RenderBlock()
    {
        int frames = sink.BlockFrames;
        double songPerFrame = Rate / sampleRate;
        Array.Clear(left);
        Array.Clear(right);
        int position = 0;
        while (position < frames)
        {
            int next = frames;
            if (cursor < events.Length)
            {
                double delta = events[cursor].Time - (blockStartSong + position * songPerFrame);
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
            double now = blockStartSong + position * songPerFrame;
            while (cursor < events.Length && events[cursor].Time <= now)
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
        reverb?.Process(left, right);
        for (int frame = 0; frame < frames; frame++)
        {
            interleaved[frame * 2] = left[frame] * MasterGain;
            interleaved[frame * 2 + 1] = right[frame] * MasterGain;
        }
        sink.Submit(interleaved);
        PeakVoices = Math.Max(PeakVoices, ActiveVoiceCount);
    }

    private void Apply(SpikeEvent item)
    {
        switch (item.Rank)
        {
            case SpikeEvent.NoteOn:
                NoteOn(item.Key, item.Value);
                break;
            case SpikeEvent.NoteOff:
                NoteOff(item.Key);
                break;
            default:
                Pedal(item.Value);
                break;
        }
    }

    private void NoteOn(int key, int velocity)
    {
        keyDown[key] = true;
        pendingRelease[key] = false;
        noteOnTime[key] = renderedSeconds;
        noteOnVelocity[key] = velocity;
        double roll = random.NextDouble();
        foreach (Prepared prepared in regions)
        {
            SfzRegion region = prepared.Region;
            if (!region.ReleaseTrigger && !region.PedalTriggered && key >= region.LoKey && key <= region.HiKey &&
                velocity >= region.LoVel && velocity <= region.HiVel && roll >= region.LoRand && roll < region.HiRand)
            {
                Start(prepared, key, velocity, 1f);
            }
        }
    }

    private void NoteOff(int key)
    {
        keyDown[key] = false;
        if (pedal >= 64)
        {
            pendingRelease[key] = true;
            return;
        }
        ReleaseKey(key);
    }

    /// <summary>The damper falls: the key's voices release and its release noises sound.</summary>
    private void ReleaseKey(int key)
    {
        pendingRelease[key] = false;
        foreach (Voice voice in voices)
        {
            if (voice.Active && voice.Key == key && !voice.Releasing && !voice.Prepared.Region.ReleaseTrigger)
            {
                voice.Release(voice.Prepared.ReleaseCoefficient);
            }
        }
        int velocity = noteOnVelocity[key];
        double held = renderedSeconds - noteOnTime[key];
        double roll = random.NextDouble();
        foreach (Prepared prepared in regions)
        {
            SfzRegion region = prepared.Region;
            if (region.ReleaseTrigger && key >= region.LoKey && key <= region.HiKey && velocity >= region.LoVel &&
                velocity <= region.HiVel && roll >= region.LoRand && roll < region.HiRand)
            {
                Start(prepared, key, velocity, (float)Math.Pow(10, -region.RtDecay * held / 20));
            }
        }
    }

    private void Pedal(int value)
    {
        int previous = pedal;
        pedal = value;
        double roll = random.NextDouble();
        foreach (Prepared prepared in regions)
        {
            SfzRegion region = prepared.Region;
            bool inside = value >= region.OnLoCc64 && value <= region.OnHiCc64;
            bool wasInside = previous >= region.OnLoCc64 && previous <= region.OnHiCc64;
            if (region.PedalTriggered && inside && !wasInside && roll >= region.LoRand && roll < region.HiRand)
            {
                Start(prepared, -1, 127, 1f);
            }
        }
        if (previous >= 64 && value < 64)
        {
            for (int key = 0; key < 128; key++)
            {
                if (pendingRelease[key] && !keyDown[key])
                {
                    ReleaseKey(key);
                }
            }
        }
    }

    private void Start(Prepared prepared, int key, int velocity, float extraGain)
    {
        SfzRegion region = prepared.Region;
        if (region.Group != 0)
        {
            float fast = (float)Math.Exp(Math.Log(1e-3) / (FastReleaseSeconds * sampleRate));
            foreach (Voice other in voices)
            {
                if (other.Active && other.Prepared.Region.OffBy == region.Group)
                {
                    other.Release(fast);
                }
            }
        }
        double normalized = velocity / 127.0;
        double track = Math.Abs(region.AmpVeltrack) / 100.0;
        float velocityGain = (float)((1 - track) + track * normalized * normalized);
        double semitones = key < 0 ? 0 : (key - region.PitchKeycenter) * region.PitchKeytrack / 100.0;
        double step = prepared.RateRatio * Math.Pow(2, (semitones + region.Tune / 100.0) / 12.0);

        Voice voice = Allocate();
        voice.Begin(prepared, key, step, prepared.VolumeGain * velocityGain * extraGain);
    }

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
        short* data = bank.Frames;
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
                short* p = data + (origin + index) * 2;
                short* before = index > 0 ? p - 2 : p;
                left[frame] += Hermite(before[0], p[0], p[2], p[4], t) * gain * envelope;
                right[frame] += Hermite(before[1], p[1], p[3], p[5], t) * gain * envelope;
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
        float c2 = before - 2.5f * here + 2f * after - 0.5f * next;
        float c3 = 0.5f * (next - before) + 1.5f * (here - after);
        return ((c3 * t + c2) * t + c1) * t + here;
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
