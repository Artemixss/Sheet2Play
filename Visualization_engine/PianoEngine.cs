namespace SynthesiaClone;

/// <summary>
/// A built-in piano that renders a <see cref="PlaybackSession"/> into an <see cref="IAudioSink"/>:
/// the SoundFont piano (<see cref="SoundFontEngine"/>) or the SFZ piano (<see cref="SfzEngine"/>).
/// </summary>
/// <remarks>
/// Both own the event schedule and place each event on its own sample, so the timebase, the
/// exporters and the audio thread treat them alike. Neither is thread-safe; the live one is wrapped
/// in <see cref="LockedPianoEngine"/>.
/// </remarks>
public interface IPianoEngine
{
    /// <summary>Song seconds of audio handed to the sink so far.</summary>
    double SubmittedSongSeconds { get; }

    /// <summary>Blocks the sink asked for while it had already run dry. Non-zero means dropouts.</summary>
    int UnderrunCount { get; }

    int ActiveVoiceCount { get; }

    bool IsRunning { get; }

    void Start();

    void Stop();

    /// <summary>Applied at the next block boundary.</summary>
    void SetRate(double value);

    /// <summary>Repositions the schedule and re-triggers whatever should already be sounding.</summary>
    void Seek(double songSeconds);

    /// <summary>Fills the sink while it wants blocks.</summary>
    void Pump();

    /// <summary>Renders exactly one block, for offline export.</summary>
    void RenderBlock();
}

/// <summary>
/// The live piano, shared between the audio thread, which pumps it, and the frame loop, which
/// starts, pauses, seeks and changes rate.
/// </summary>
/// <remarks>
/// Every call that touches the engine takes one lock, so a seek never lands inside a block render.
/// The two values the frame loop reads every frame - song time and whether it is running - are
/// published after each locked call and read without the lock: the frame loop must never wait out
/// a block render (up to 16 ms on the densest song) just to draw.
/// </remarks>
public sealed class LockedPianoEngine : IPianoEngine
{
    private readonly IPianoEngine inner;
    private readonly object gate;
    private double submitted;
    private volatile bool running;

    public LockedPianoEngine(IPianoEngine inner, object gate)
    {
        this.inner = inner ?? throw new ArgumentNullException(nameof(inner));
        this.gate = gate ?? throw new ArgumentNullException(nameof(gate));
        Publish();
    }

    public double SubmittedSongSeconds => Volatile.Read(ref submitted);
    public bool IsRunning => running;
    public int UnderrunCount => inner.UnderrunCount;
    public int ActiveVoiceCount => inner.ActiveVoiceCount;

    public void Start() => Locked(inner.Start);
    public void Stop() => Locked(inner.Stop);
    public void SetRate(double value) => Locked(() => inner.SetRate(value));
    public void Seek(double songSeconds) => Locked(() => inner.Seek(songSeconds));
    // Written out rather than through Locked: the audio thread calls this every millisecond, and the
    // render path must not allocate (a gen-2 collection mid-song is an audible dropout).
    public void Pump()
    {
        lock (gate)
        {
            inner.Pump();
            Publish();
        }
    }

    public void RenderBlock()
    {
        lock (gate)
        {
            inner.RenderBlock();
            Publish();
        }
    }

    private void Locked(Action action)
    {
        lock (gate)
        {
            action();
            Publish();
        }
    }

    private void Publish()
    {
        Volatile.Write(ref submitted, inner.SubmittedSongSeconds);
        running = inner.IsRunning;
    }
}
