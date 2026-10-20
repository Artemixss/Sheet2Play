using System.Runtime.InteropServices;
using MeltySynth;

namespace SynthesiaClone;

/// <summary>
/// What the UI needs to say about audio, as plain data.
/// </summary>
/// <remarks>
/// Passed to the drawing code rather than letting it query the audio system, so
/// <c>--smoke</c> can fabricate any state - including the degraded ones - and still render a
/// reproducible PNG on a machine with no audio device and no soundfont.
/// </remarks>
/// <param name="Piano">The SFZ piano playing, when <see cref="Backend"/> is <see cref="AudioBackend.SfzPiano"/>.</param>
public sealed record AudioOutputStatus(
    AudioBackend Backend,
    string? SoundFontName,
    long SoundFontBytes,
    string? DeviceName,
    string? Problem,
    PianoDescription? Piano = null)
{
    public bool IsSilent => Backend switch
    {
        AudioBackend.SoundFont => SoundFontName is null,
        AudioBackend.SfzPiano => Piano is null,
        _ => true
    };
}

/// <summary>
/// Owns whichever output is actually making sound, and mints a timebase per song.
/// </summary>
/// <remarks>
/// The pianos (SoundFont and SFZ) render the audio here, so they own the schedule and report song
/// time from the samples they have produced. Nothing is pushed to them, so their
/// <see cref="IMidiOutput"/> is the null sink and every note reaches them through the timebase.
/// With no piano at all, song time comes from a stopwatch and the app plays silently.
///
/// The built-in pianos render on their own audio thread, not in the frame loop: the SFZ piano's
/// worst block on the densest song took three quarters of its budget in Phase 4a, which leaves no
/// room for a frame being drawn on the same thread.
///
/// Selection resolves before it defaults: asking for the SFZ piano when it is not installed falls
/// back to the SoundFont piano, and with neither the app runs silently and says how to install one.
/// The external MIDI device was removed on 2026-10-20 at the user's request ("let it be only 2
/// pianos"); a setting that still names it opens the SFZ piano.
/// </remarks>
public sealed class AudioOutput : IDisposable
{
    /// <summary>
    /// 48kHz because Windows shared-mode WASAPI usually runs there, so anything else makes
    /// the mixer resample on the way out.
    /// </summary>
    public const int SampleRate = 48000;

    /// <summary>
    /// One sub-buffer. Two are in flight, so this is 42.7ms of audio at 48kHz - enough slack
    /// to survive an ordinary frame hitch without a dropout, while staying short enough that
    /// the offset it forces is small.
    /// </summary>
    public const int BlockFrames = 1024;

    private readonly SoundFont? soundFont;
    private readonly SfzPiano? sfzPiano;
    private readonly RaylibAudioSink? sink;
    private readonly object engineGate = new();
    private readonly Thread? audioThread;
    private volatile LockedPianoEngine? engine;
    private volatile bool disposing;
    private SoundFontTimebase? timebase;

    private AudioOutput(
        AudioBackend backend,
        SoundFont? soundFont,
        SfzPiano? sfzPiano,
        RaylibAudioSink? sink,
        AudioOutputStatus status)
    {
        Backend = backend;
        this.soundFont = soundFont;
        this.sfzPiano = sfzPiano;
        this.sink = sink;
        // Nothing is pushed to a piano; it plays from the timebase's schedule.
        MidiOutput = new NullMidiOutput();
        Status = status;
        if (sink is not null)
        {
            // Sleep(1) has to mean about a millisecond, not the default 15.6 ms timer tick.
            timeBeginPeriod(1);
            audioThread = new Thread(RunAudio)
            {
                Name = "Sheet2Play audio",
                IsBackground = true,
                Priority = ThreadPriority.Highest
            };
            audioThread.Start();
        }
    }

    public AudioBackend Backend { get; }
    public IMidiOutput MidiOutput { get; }
    public AudioOutputStatus Status { get; }

    /// <summary>True when a built-in piano is playing, so offline export can render the same sound.</summary>
    public bool CanRender => soundFont is not null || sfzPiano is not null;

    /// <summary>Seconds of audio in flight, which is the latency the offset has to cover.</summary>
    public double BufferedSeconds => sink?.BufferedSeconds ?? 0;

    public int UnderrunCount => engine?.UnderrunCount ?? 0;

    /// <summary>Silences the stream without stopping it, so a measurement still runs in real time.</summary>
    public void Mute() => sink?.SetVolume(0f);

    /// <summary>
    /// Opens the requested backend, falling back when it cannot be had. Never throws: a machine
    /// with no audio at all still runs and visualises.
    /// </summary>
    public static AudioOutput Create(AudioBackend preferred, string? soundFontPath)
    {
        string? carriedProblem = null;
        preferred = preferred.Offered();
        if (preferred == AudioBackend.SfzPiano)
        {
            (SfzPiano? piano, PianoStatus pianoStatus) = PianoLibrary.Load();
            if (piano is not null)
            {
                (RaylibAudioSink? audioSink, string? audioProblem) = RaylibAudioSink.TryCreate(SampleRate, BlockFrames);
                if (audioSink is not null)
                {
                    Console.WriteLine($"[AUDIO] built-in SFZ piano, {piano.Description.Name} " +
                        $"({pianoStatus.Bytes / 1024.0 / 1024.0:0} MB bank), " +
                        $"{audioSink.BufferedSeconds * 1000:0} ms buffered");
                    return new AudioOutput(
                        AudioBackend.SfzPiano,
                        null,
                        piano,
                        audioSink,
                        new AudioOutputStatus(AudioBackend.SfzPiano, null, pianoStatus.Bytes, null, null, piano.Description));
                }
                Console.Error.WriteLine("[AUDIO] " + audioProblem);
                return CreateSilent(audioProblem);
            }
            Console.Error.WriteLine("[AUDIO] " + pianoStatus.Problem);
            // Not installed is not a reason to go silent: the SoundFont piano is the next best.
            carriedProblem = pianoStatus.Problem;
            preferred = AudioBackend.SoundFont;
        }

        if (preferred == AudioBackend.SoundFont)
        {
            (SoundFont? font, SoundFontStatus fontStatus) = SoundFontLibrary.Load(soundFontPath);
            if (font is not null)
            {
                (RaylibAudioSink? audioSink, string? audioProblem) = RaylibAudioSink.TryCreate(SampleRate, BlockFrames);
                if (audioSink is not null)
                {
                    Console.WriteLine($"[AUDIO] built-in synth, {fontStatus.Name} " +
                        $"({fontStatus.Bytes / 1024.0 / 1024.0:0.0} MB), " +
                        $"{audioSink.BufferedSeconds * 1000:0} ms buffered");
                    return new AudioOutput(
                        AudioBackend.SoundFont,
                        font,
                        null,
                        audioSink,
                        new AudioOutputStatus(
                            AudioBackend.SoundFont, fontStatus.Name, fontStatus.Bytes, null, carriedProblem));
                }
                Console.Error.WriteLine("[AUDIO] " + audioProblem);
                return CreateSilent(audioProblem);
            }
            Console.Error.WriteLine("[AUDIO] " + fontStatus.Problem);
            // Salamander was asked for and is missing too, so neither piano can play.
            return CreateSilent(carriedProblem is null ? fontStatus.Problem : NoPianoProblem);
        }

        return CreateSilent(NoPianoProblem);
    }

    /// <summary>What the home screen says when neither piano is installed.</summary>
    public const string NoPianoProblem =
        "No piano is installed, so playback is silent. Run scripts\\install-piano.ps1 for Salamander, then pick it under PIANO.";

    /// <summary>Plays nothing: song time comes from a stopwatch, so the notes still fall.</summary>
    private static AudioOutput CreateSilent(string? problem) =>
        new(AudioBackend.Silent, null, null, null, new AudioOutputStatus(AudioBackend.Silent, null, 0, null, problem));

    /// <summary>
    /// A piano of the kind playing now, for an offline render into <paramref name="target"/>, or
    /// null when none is playing. Safe to use
    /// on another thread: it shares only the read-only SoundFont or SFZ bank.
    /// </summary>
    public IPianoEngine? CreateOfflineEngine(IAudioSink target, PlaybackSession session, int sampleRate)
    {
        ArgumentNullException.ThrowIfNull(target);
        ArgumentNullException.ThrowIfNull(session);
        if (sfzPiano is not null)
        {
            return new SfzEngine(sfzPiano, target, session, sampleRate);
        }
        return soundFont is null ? null : new SoundFontEngine(soundFont, target, session, sampleRate);
    }

    /// <summary>
    /// Builds the clock for a song. A piano returns a timebase that owns the audio; with none, the
    /// stopwatch clock keeps the notes falling in silence.
    /// </summary>
    public IPlaybackTimebase CreateTimebase(PlaybackSession session, double audioOffsetSeconds)
    {
        ArgumentNullException.ThrowIfNull(session);
        if (sink is null || !CanRender)
        {
            return new PlaybackClock();
        }

        // A fresh engine per song, sharing the already-loaded samples. Swapped in under the lock,
        // so the audio thread finishes the old song's block before it starts on the new one.
        IPianoEngine inner = CreateOfflineEngine(sink, session, SampleRate)!;
        LockedPianoEngine newEngine = new(inner, engineGate);
        lock (engineGate)
        {
            engine = newEngine;
        }
        SoundFontTimebase newTimebase = new(newEngine, sink.BlockPeriodSeconds);
        newTimebase.SetOutputLatencySeconds(audioOffsetSeconds);
        timebase = newTimebase;
        return newTimebase;
    }

    /// <summary>
    /// Re-anchors song time to the audio rendered so far. Cheap, and called every frame.
    /// </summary>
    /// <remarks>
    /// The audio thread keeps the stream fed; this only reads where it has got to. It does nothing
    /// until a song has been loaded, because the engine is built per song in
    /// <see cref="CreateTimebase"/>, and after returning Home the engine keeps rendering silence.
    /// </remarks>
    public void Pump() => timebase?.Latch();

    /// <summary>
    /// Feeds the stream whenever a sub-buffer frees up. A millisecond's poll is far inside the
    /// 21 ms a sub-buffer lasts, and Raylib's stream calls take its own lock, so this thread may
    /// use them while the frame loop draws.
    /// </summary>
    private void RunAudio()
    {
        while (!disposing)
        {
            try
            {
                engine?.Pump();
            }
            catch (Exception error)
            {
                // A failure here would otherwise kill the process from a background thread.
                Console.Error.WriteLine("[AUDIO] Render failed: " + error);
                engine = null;
            }
            Thread.Sleep(1);
        }
    }

    public void Dispose()
    {
        if (disposing)
        {
            return;
        }
        disposing = true;
        // The thread stops before the stream it writes to is released.
        audioThread?.Join();
        if (audioThread is not null)
        {
            timeEndPeriod(1);
        }
        sink?.Dispose();
    }

    [DllImport("winmm.dll")]
    private static extern uint timeBeginPeriod(uint milliseconds);

    [DllImport("winmm.dll")]
    private static extern uint timeEndPeriod(uint milliseconds);
}
