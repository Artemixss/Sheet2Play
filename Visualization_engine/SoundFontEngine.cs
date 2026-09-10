using System.Diagnostics;
using MeltySynth;

namespace SynthesiaClone;

/// <summary>
/// Where rendered audio goes. Implemented by the live audio stream and by the file writer,
/// so the same engine drives playback and offline export.
/// </summary>
public interface IAudioSink
{
    /// <summary>Frames per block. The engine always submits exactly this many.</summary>
    int BlockFrames { get; }

    /// <summary>True when the sink can take another block right now.</summary>
    bool WantsBlock { get; }

    /// <summary>Takes one block of interleaved stereo float samples.</summary>
    void Submit(ReadOnlySpan<float> interleaved);
}

/// <summary>
/// Renders a <see cref="PlaybackSession"/> to audio with a SoundFont, placing each note on
/// an exact sample rather than on a frame boundary.
/// </summary>
/// <remarks>
/// The engine owns the event schedule instead of receiving pushed notes, which is the whole
/// point: it can split a render block at every onset inside it, so a chord's notes land on
/// the samples the score asks for even though the render loop only wakes up every few
/// milliseconds.
///
/// One caveat worth stating precisely rather than claiming more than is true: MeltySynth
/// buffers internally in <see cref="SynthesizerSettings.BlockSize"/> chunks, so a note takes
/// effect at the next internal block boundary. <see cref="OnsetResolutionSamples"/> is set
/// small enough that this is well under a millisecond - two orders below the 7-17ms frame
/// grid it replaces, and below the threshold where onset error is audible.
///
/// Not thread-safe, because MeltySynth is not. One instance per thread; the offline exporter
/// builds its own and shares only the immutable <see cref="MeltySynth.SoundFont"/>.
/// </remarks>
public sealed class SoundFontEngine
{
    /// <summary>
    /// MeltySynth's internal render granularity, and therefore the real onset resolution.
    /// 16 samples is a third of a millisecond at 48kHz. The default is 64; the cost of
    /// lowering it is a little more per-block overhead, which is irrelevant next to the
    /// sample interpolation itself.
    /// </summary>
    public const int OnsetResolutionSamples = 16;

    /// <summary>
    /// Held notes accumulate at low playback rates, and generated pedal will add more.
    /// MeltySynth's default of 64 steals voices - which cuts notes off mid-sustain and
    /// sounds exactly like the sample library misbehaving.
    /// </summary>
    public const int MaximumPolyphony = 256;

    private readonly Synthesizer synthesizer;
    private readonly IAudioSink sink;
    private readonly PlaybackEvent[] events;
    private readonly int sampleRate;

    // Allocated once. The render path must not allocate: a gen-2 collection mid-song is an
    // audible dropout.
    private readonly float[] left;
    private readonly float[] right;
    private readonly float[] interleaved;

    private int cursor;
    private double blockStartSong;
    private double rate = 1.0;
    private double stagedRate = 1.0;
    private bool running;

    public SoundFontEngine(SoundFont soundFont, IAudioSink sink, PlaybackSession session, int sampleRate)
    {
        ArgumentNullException.ThrowIfNull(soundFont);
        ArgumentNullException.ThrowIfNull(session);
        this.sink = sink ?? throw new ArgumentNullException(nameof(sink));
        this.sampleRate = sampleRate > 0
            ? sampleRate
            : throw new ArgumentOutOfRangeException(nameof(sampleRate), sampleRate, "Sample rate must be positive.");

        synthesizer = new Synthesizer(soundFont, new SynthesizerSettings(sampleRate)
        {
            BlockSize = OnsetResolutionSamples,
            MaximumPolyphony = MaximumPolyphony,
            // Reverb is one of the three things that separates a good render from the dry,
            // harsh one an external synth gives us. On by default, deliberately.
            EnableReverbAndChorus = true
        });

        events = session.Events;
        left = new float[sink.BlockFrames];
        right = new float[sink.BlockFrames];
        interleaved = new float[sink.BlockFrames * 2];
    }

    /// <summary>Song seconds of audio handed to the sink so far.</summary>
    public double SubmittedSongSeconds => blockStartSong;

    /// <summary>Blocks the sink asked for while it had already run dry. Non-zero means dropouts.</summary>
    public int UnderrunCount { get; private set; }

    public int ActiveVoiceCount => synthesizer.ActiveVoiceCount;

    public bool IsRunning => running;

    public void Start() => running = true;

    public void Stop()
    {
        running = false;
        // Release rather than cut: the envelopes and the reverb tail keep decaying, which is
        // what a piano does when you stop playing it.
        synthesizer.NoteOffAll(immediate: false);
    }

    /// <summary>
    /// Staged rather than applied, because a rate change part-way through a block would
    /// desynchronise the song-time accounting. Picked up at the next block boundary, at most
    /// one block later - inaudible.
    /// </summary>
    public void SetRate(double value) => stagedRate = value;

    /// <summary>
    /// Repositions the schedule and re-triggers whatever should already be sounding.
    /// </summary>
    public void Seek(double songSeconds)
    {
        synthesizer.NoteOffAll(immediate: true);
        synthesizer.Reset();
        blockStartSong = Math.Max(0, songSeconds);
        cursor = UpperBound(blockStartSong);

        // Re-trigger notes that started before this point and have not ended, so seeking into
        // a held chord does not land in silence. Their real velocities come from the events,
        // which is why the engine keeps the schedule rather than a count of active pitches.
        Span<int> depth = stackalloc int[88];
        Span<int> velocity = stackalloc int[88];
        for (int index = 0; index < cursor; index++)
        {
            PlaybackEvent item = events[index];
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
        for (int keyIndex = 0; keyIndex < depth.Length; keyIndex++)
        {
            if (depth[keyIndex] > 0)
            {
                synthesizer.NoteOn(0, keyIndex + 21, velocity[keyIndex]);
            }
        }
    }

    /// <summary>
    /// Fills the sink while it wants blocks. Cheap and safe to call every frame.
    /// </summary>
    public void Pump()
    {
        // A raylib stream holds two sub-buffers, so this loop runs at most twice. Rendering two in
        // one pass means both were free on entry - the stream had already run dry and the gap was
        // heard as a dropout.
        //
        // The previous version of this check asked the sink whether it was starved AFTER the loop,
        // which could never be true: the loop only exits once the sink stops wanting blocks, so the
        // final Submit always cleared the flag. It counted zero underruns no matter what happened,
        // which is worse than no counter at all - it reads as evidence that there were none.
        int rendered = 0;
        while (sink.WantsBlock)
        {
            RenderBlock();
            rendered++;
        }
        if (rendered > 1)
        {
            UnderrunCount++;
        }
    }

    /// <summary>
    /// Renders exactly one block, stopping at every scheduled event inside it so the event
    /// applies at its own sample.
    /// </summary>
    /// <remarks>
    /// Always submits a full block. A short write is either zero-padded or rejected depending
    /// on the sink, and both show up as clicks.
    /// </remarks>
    internal void RenderBlock()
    {
        int frames = sink.BlockFrames;
        rate = stagedRate;

        // Paused: render the block anyway so tails and reverb decay, but do not advance song
        // time or the cursor. This reproduces PlaybackClock's pause semantics for free.
        double songPerFrame = running ? rate / sampleRate : 0.0;

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
                synthesizer.Render(left.AsSpan(position, next - position), right.AsSpan(position, next - position));
                position = next;
            }

            if (songPerFrame <= 0)
            {
                break;
            }

            double timeHere = blockStartSong + (position * songPerFrame);
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

        for (int frame = 0; frame < frames; frame++)
        {
            interleaved[frame * 2] = left[frame];
            interleaved[(frame * 2) + 1] = right[frame];
        }
        sink.Submit(interleaved);
    }

    private void Apply(PlaybackEvent item)
    {
        if (item.IsNoteOn)
        {
            synthesizer.NoteOn(0, item.KeyIndex + 21, item.Velocity);
        }
        else
        {
            synthesizer.NoteOff(0, item.KeyIndex + 21);
        }
    }

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
}

/// <summary>
/// Implemented by sinks that can tell whether they ran dry before being refilled.
/// </summary>
public interface IUnderrunAware
{
    bool WasStarved { get; }
}

/// <summary>
/// Song time as told by the audio that has actually been rendered.
/// </summary>
/// <remarks>
/// This is the master clock when the built-in synth is playing: no <see cref="Stopwatch"/>
/// decides when a note sounds, so the falling notes track what is being heard by
/// construction rather than by calibration.
///
/// The rendered position only advances once per block, so returning it raw would make the
/// notes visibly staircase. It is interpolated with a stopwatch between blocks and clamped at
/// both ends - the upper clamp stops the interpolation overrunning and snapping back, the
/// lower one keeps <see cref="Position"/> monotonic so the visual cursor cannot re-fire
/// events it has already passed.
/// </remarks>
public sealed class SoundFontTimebase : IPlaybackTimebase
{
    private readonly SoundFontEngine engine;
    private readonly Func<double> timestampSeconds;
    private readonly double blockPeriodSeconds;

    private double latchedSong;
    // Sentinel rather than 0, so the very first latch at song position 0 is not mistaken for
    // "nothing new has been rendered".
    private double lastLatchedSubmitted = double.NaN;
    private double latchedAt;
    private double lastReturned;
    private double outputLatencySeconds;
    private double playbackRate = 1.0;

    public SoundFontTimebase(
        SoundFontEngine engine,
        double blockPeriodSeconds,
        Func<double>? timestampSeconds = null)
    {
        this.engine = engine ?? throw new ArgumentNullException(nameof(engine));
        this.blockPeriodSeconds = blockPeriodSeconds > 0
            ? blockPeriodSeconds
            : throw new ArgumentOutOfRangeException(nameof(blockPeriodSeconds));
        this.timestampSeconds = timestampSeconds ?? DefaultTimestampSeconds;
        latchedAt = this.timestampSeconds();
    }

    public bool IsRunning => engine.IsRunning;
    public double PlaybackRate => playbackRate;
    public bool OwnsAudioDispatch => true;

    public double Position
    {
        get
        {
            if (!engine.IsRunning)
            {
                lastReturned = Math.Max(0, latchedSong);
                return lastReturned;
            }

            double elapsed = Math.Max(0, timestampSeconds() - latchedAt);
            double interpolated = latchedSong + (elapsed * playbackRate);
            double ceiling = latchedSong + (blockPeriodSeconds * playbackRate);
            double clamped = Math.Clamp(interpolated, lastReturned, Math.Max(lastReturned, ceiling));
            lastReturned = clamped;
            return clamped;
        }
    }

    /// <summary>
    /// Called after the engine has been topped up, to re-anchor the interpolation.
    /// </summary>
    /// <summary>
    /// Re-anchors the interpolation, but only when the engine has actually produced more audio.
    /// </summary>
    /// <remarks>
    /// The conditional is the whole point. This is called every frame from the pump, while a block
    /// is only submitted about every third frame at 144Hz. Re-anchoring unconditionally reset
    /// <c>latchedAt</c> to now while <c>latchedSong</c> stood still, so the elapsed term could never
    /// accumulate and <see cref="Position"/> returned the block position every time - collapsing the
    /// motion into a 46.875Hz staircase, which is exactly what the interpolation exists to prevent.
    /// The frame rate stayed at 144 throughout, so it looked like dropped frames without being any.
    /// </remarks>
    public void Latch()
    {
        double submitted = engine.SubmittedSongSeconds;
        if (submitted == lastLatchedSubmitted)
        {
            return;
        }
        Reanchor();
    }

    /// <summary>
    /// Forces a re-anchor. Used where song time moves for a reason other than rendering - a seek, a
    /// rate change, or a new output latency - and the previous anchor is meaningless.
    /// </summary>
    private void Reanchor()
    {
        lastLatchedSubmitted = engine.SubmittedSongSeconds;
        latchedSong = Math.Max(0, lastLatchedSubmitted - (outputLatencySeconds * playbackRate));
        latchedAt = timestampSeconds();
    }

    public void SetOutputLatencySeconds(double seconds)
    {
        outputLatencySeconds = Math.Max(0, seconds);
        Reanchor();
    }

    public void SetPlaybackRate(double rate)
    {
        if (!double.IsFinite(rate) ||
            rate is < PlaybackRateRules.Minimum or > PlaybackRateRules.Maximum)
        {
            throw new ArgumentOutOfRangeException(
                nameof(rate),
                rate,
                $"Playback rate must be between {PlaybackRateRules.Minimum:0.00}x and " +
                $"{PlaybackRateRules.Maximum:0.00}x.");
        }
        playbackRate = rate;
        engine.SetRate(rate);
        Reanchor();
    }

    public void Reset(double position, bool running)
    {
        engine.Seek(position);
        lastReturned = 0;
        Reanchor();
        if (running)
        {
            engine.Start();
        }
        else
        {
            engine.Stop();
        }
    }

    public void Pause() => engine.Stop();

    public void Resume()
    {
        Reanchor();
        engine.Start();
    }

    public void Seek(double position)
    {
        engine.Seek(position);
        lastReturned = 0;
        Reanchor();
    }

    private static double DefaultTimestampSeconds() =>
        Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
}
