using MeltySynth;
using Melanchall.DryWetMidi.Multimedia;

namespace SynthesiaClone;

/// <summary>
/// What the UI needs to say about audio, as plain data.
/// </summary>
/// <remarks>
/// Passed to the drawing code rather than letting it query the audio system, so
/// <c>--smoke</c> can fabricate any state - including the degraded ones - and still render a
/// reproducible PNG on a machine with no audio device and no soundfont.
/// </remarks>
public sealed record AudioOutputStatus(
    AudioBackend Backend,
    string? SoundFontName,
    long SoundFontBytes,
    string? DeviceName,
    string? Problem)
{
    public bool IsSilent => Backend switch
    {
        AudioBackend.SoundFont => SoundFontName is null,
        _ => DeviceName is null
    };
}

/// <summary>
/// Owns whichever output is actually making sound, and mints a timebase per song.
/// </summary>
/// <remarks>
/// The two backends differ in more than timbre, which is why this exists rather than a single
/// <see cref="IMidiOutput"/>:
///
/// - An external MIDI device is a push target. Notes go out early by the audio offset to cover
///   the synthesiser's latency, and song time comes from a stopwatch.
/// - The built-in synth renders the audio here, so it owns the schedule and reports song time
///   from the samples it has produced. Nothing is pushed to it, so its
///   <see cref="IMidiOutput"/> is the null sink and every note reaches it through the timebase.
///
/// Selection resolves before it defaults: asking for the synth on a machine with no soundfont
/// falls back to the MIDI device rather than going silent, and says so.
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
    private readonly RaylibAudioSink? sink;
    private readonly OutputDevice? outputDevice;
    private SoundFontEngine? engine;
    private SoundFontTimebase? timebase;

    private AudioOutput(
        AudioBackend backend,
        SoundFont? soundFont,
        RaylibAudioSink? sink,
        OutputDevice? outputDevice,
        IMidiOutput midiOutput,
        AudioOutputStatus status)
    {
        Backend = backend;
        this.soundFont = soundFont;
        this.sink = sink;
        this.outputDevice = outputDevice;
        MidiOutput = midiOutput;
        Status = status;
    }

    public AudioBackend Backend { get; }
    public IMidiOutput MidiOutput { get; }
    public AudioOutputStatus Status { get; }

    /// <summary>The immutable soundfont, shared with the offline exporter rather than reloaded.</summary>
    public SoundFont? SoundFont => soundFont;

    /// <summary>Seconds of audio in flight, which is the latency the offset has to cover.</summary>
    public double BufferedSeconds => sink?.BufferedSeconds ?? 0;

    public int UnderrunCount => engine?.UnderrunCount ?? 0;

    /// <summary>
    /// Opens the requested backend, falling back to the other when it cannot be had. Never
    /// throws: a machine with no audio at all still runs and visualises.
    /// </summary>
    public static AudioOutput Create(AudioBackend preferred, string? soundFontPath)
    {
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
                        audioSink,
                        outputDevice: null,
                        // Nothing is pushed to the synth; it plays from the timebase's schedule.
                        midiOutput: new NullMidiOutput(),
                        new AudioOutputStatus(
                            AudioBackend.SoundFont, fontStatus.Name, fontStatus.Bytes, null, null));
                }
                Console.Error.WriteLine("[AUDIO] " + audioProblem);
                return CreateMidiDevice(audioProblem);
            }
            Console.Error.WriteLine("[AUDIO] " + fontStatus.Problem);
            return CreateMidiDevice(fontStatus.Problem);
        }

        return CreateMidiDevice(null);
    }

    private static AudioOutput CreateMidiDevice(string? carriedProblem)
    {
        OutputDevice? device = TryOpenMidiDevice(out string? deviceProblem);
        if (device is null)
        {
            return new AudioOutput(
                AudioBackend.MidiDevice,
                null,
                null,
                null,
                new NullMidiOutput(),
                new AudioOutputStatus(
                    AudioBackend.MidiDevice, null, 0, null, carriedProblem ?? deviceProblem));
        }

        device.PrepareForEventsSending();
        IMidiOutput output = new DryWetMidiOutput(device);
        output.AllNotesOff();
        return new AudioOutput(
            AudioBackend.MidiDevice,
            null,
            null,
            device,
            output,
            new AudioOutputStatus(AudioBackend.MidiDevice, null, 0, device.Name, carriedProblem));
    }

    /// <summary>
    /// Opens a MIDI synthesiser, preferring VirtualMIDISynth and falling back to any available
    /// device. Returns null when the machine has no MIDI output at all; the caller then runs
    /// silently rather than failing to start.
    /// </summary>
    private static OutputDevice? TryOpenMidiDevice(out string? problem)
    {
        problem = null;
        try
        {
            OutputDevice byName = OutputDevice.GetByName("VirtualMIDISynth #1");
            Console.WriteLine("[AUDIO SYSTEM] Connected to VirtualMIDISynth.");
            return byName;
        }
        catch (Exception missingPreferred)
        {
            OutputDevice? fallback;
            try
            {
                fallback = OutputDevice.GetAll().FirstOrDefault();
            }
            catch (Exception discovery)
            {
                Console.Error.WriteLine("[AUDIO SYSTEM] Could not enumerate MIDI devices. " + discovery.Message);
                fallback = null;
            }

            if (fallback is null)
            {
                problem = "No MIDI output device found. Playback is silent; install a MIDI " +
                    "synthesizer such as VirtualMIDISynth, or use the built-in synth.";
                Console.Error.WriteLine("[AUDIO SYSTEM] " + problem + " " + missingPreferred.Message);
                return null;
            }

            Console.Error.WriteLine(
                "[AUDIO SYSTEM] VirtualMIDISynth unavailable; using " + fallback.Name +
                ". " + missingPreferred.Message);
            return fallback;
        }
    }

    /// <summary>
    /// Builds the clock for a song. The synth backend returns a timebase that owns the audio;
    /// the MIDI backend returns the stopwatch clock the app has always used.
    /// </summary>
    public IPlaybackTimebase CreateTimebase(PlaybackSession session, double audioOffsetSeconds)
    {
        ArgumentNullException.ThrowIfNull(session);
        if (soundFont is null || sink is null)
        {
            return new PlaybackClock();
        }

        // A fresh Synthesizer per song, sharing the already-parsed SoundFont so the sample data
        // is not read again.
        engine = new SoundFontEngine(soundFont, sink, session, SampleRate);
        SoundFontTimebase newTimebase = new(engine, sink.BlockPeriodSeconds);
        newTimebase.SetOutputLatencySeconds(audioOffsetSeconds);
        timebase = newTimebase;
        return newTimebase;
    }

    /// <summary>
    /// Keeps the audio stream fed and re-anchors song time. Cheap, and called every frame.
    /// </summary>
    /// <remarks>
    /// It does nothing until a song has been loaded, because the engine is built per song in
    /// <see cref="CreateTimebase"/>. An earlier comment here claimed the stream was kept fed "on
    /// every screen", which was not true before the first load - and after returning Home the engine
    /// keeps rendering silence rather than stopping. Neither is expensive, but the comment was
    /// describing intent rather than behaviour.
    /// </remarks>
    public void Pump()
    {
        if (engine is null)
        {
            return;
        }
        engine.Pump();
        timebase?.Latch();
    }

    public void Dispose()
    {
        sink?.Dispose();
        outputDevice?.Dispose();
    }
}
