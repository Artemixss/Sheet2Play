using System.Diagnostics;
using System.Collections.Concurrent;
using Melanchall.DryWetMidi.Common;
using Melanchall.DryWetMidi.Core;
using Melanchall.DryWetMidi.Multimedia;

namespace SynthesiaClone;

public sealed record LoadCompletion<T>(T? Value, Exception? Error) where T : class;

public sealed class LoadResultHandoff<T> where T : class
{
    private readonly ConcurrentQueue<LoadCompletion<T>> completions = new();

    public void Complete(T value)
    {
        ArgumentNullException.ThrowIfNull(value);
        completions.Enqueue(new LoadCompletion<T>(value, null));
    }

    public void Fail(Exception error)
    {
        ArgumentNullException.ThrowIfNull(error);
        completions.Enqueue(new LoadCompletion<T>(null, error));
    }

    public bool TryTake(out LoadCompletion<T>? completion) =>
        completions.TryDequeue(out completion);
}

public interface IMidiOutput
{
    void NoteOn(int midiPitch, int velocity);
    void NoteOff(int midiPitch);
    void AllNotesOff();
}

/// <summary>
/// Discards every note. Used when no MIDI synthesiser is installed, so the app still
/// runs and visualises silently instead of failing to start.
/// </summary>
public sealed class NullMidiOutput : IMidiOutput
{
    public void NoteOn(int midiPitch, int velocity)
    {
    }

    public void NoteOff(int midiPitch)
    {
    }

    public void AllNotesOff()
    {
    }
}

public sealed class DryWetMidiOutput(OutputDevice outputDevice) : IMidiOutput
{
    private readonly OutputDevice outputDevice = outputDevice
        ?? throw new ArgumentNullException(nameof(outputDevice));

    public void NoteOn(int midiPitch, int velocity)
    {
        outputDevice.SendEvent(new NoteOnEvent(
            (SevenBitNumber)ValidateMidiValue(midiPitch, nameof(midiPitch)),
            (SevenBitNumber)ValidateMidiValue(velocity, nameof(velocity))));
    }

    public void NoteOff(int midiPitch)
    {
        outputDevice.SendEvent(new NoteOffEvent(
            (SevenBitNumber)ValidateMidiValue(midiPitch, nameof(midiPitch)),
            (SevenBitNumber)0));
    }

    public void AllNotesOff()
    {
        for (int pitch = 21; pitch <= 108; pitch++)
        {
            NoteOff(pitch);
        }
    }

    private static byte ValidateMidiValue(int value, string parameterName)
    {
        if (value is < 0 or > 127)
        {
            throw new ArgumentOutOfRangeException(parameterName, value, "MIDI values must be between 0 and 127.");
        }
        return (byte)value;
    }
}

public sealed class PlaybackClock
{
    private readonly Func<double> timestampSeconds;
    private double baselinePosition;
    private double baselineTimestamp;
    private double playbackRate = 1.0;

    public PlaybackClock(Func<double>? timestampSeconds = null)
    {
        this.timestampSeconds = timestampSeconds ?? DefaultTimestampSeconds;
        baselineTimestamp = this.timestampSeconds();
    }

    public bool IsRunning { get; private set; }
    public double PlaybackRate => playbackRate;

    public double Position => IsRunning
        ? baselinePosition + Math.Max(0, timestampSeconds() - baselineTimestamp) * playbackRate
        : baselinePosition;

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
        baselinePosition = Position;
        baselineTimestamp = timestampSeconds();
        playbackRate = rate;
    }

    public void Reset(double position, bool running)
    {
        baselinePosition = ValidatePosition(position);
        baselineTimestamp = timestampSeconds();
        IsRunning = running;
    }

    public void Pause()
    {
        if (!IsRunning)
        {
            return;
        }
        baselinePosition = Position;
        IsRunning = false;
    }

    public void Resume()
    {
        if (IsRunning)
        {
            return;
        }
        baselineTimestamp = timestampSeconds();
        IsRunning = true;
    }

    public void Seek(double position)
    {
        baselinePosition = ValidatePosition(position);
        baselineTimestamp = timestampSeconds();
    }

    private static double DefaultTimestampSeconds() =>
        Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;

    private static double ValidatePosition(double position)
    {
        if (!double.IsFinite(position) || position < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(position), position, "Playback position must be finite and non-negative.");
        }
        return position;
    }
}

public sealed class PlaybackSession
{
    private readonly Note[] notes;
    private readonly IReadOnlyList<Note> readOnlyNotes;

    public PlaybackSession(IEnumerable<Note> sourceNotes, double audioOffsetSeconds = 0.055)
    {
        ArgumentNullException.ThrowIfNull(sourceNotes);
        if (!double.IsFinite(audioOffsetSeconds) || audioOffsetSeconds < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(audioOffsetSeconds));
        }

        Note[] candidates = sourceNotes.OrderBy(note => note.StartTime)
            .ThenBy(note => note.TargetKeyIndex)
            .ThenBy(note => note.Duration)
            .ToArray();

        // Zero-length and out-of-range notes occur in real MIDI files and in OMR output.
        // Drop them rather than throwing: one unplayable note must not sink the whole song.
        notes = candidates.Where(IsPlayable).ToArray();
        int skipped = candidates.Length - notes.Length;
        if (skipped > 0)
        {
            Console.Error.WriteLine(
                $"[PLAYBACK] Skipped {skipped} unplayable note(s) of {candidates.Length} " +
                "(zero/negative duration, out-of-range key, or non-finite timing).");
        }

        readOnlyNotes = Array.AsReadOnly(notes);
        if (notes.Length == 0)
        {
            throw new ArgumentException("A playback session requires at least one playable note.", nameof(sourceNotes));
        }

        TotalDuration = notes.Max(note => note.EndTime);
        MaxNoteDuration = notes.Max(note => note.Duration);
        Events = notes.SelectMany(note => new[]
            {
                new PlaybackEvent(Math.Max(0, note.StartTime - audioOffsetSeconds), note.TargetKeyIndex, note.Velocity, true),
                new PlaybackEvent(Math.Max(0, note.EndTime - audioOffsetSeconds), note.TargetKeyIndex, note.Velocity, false)
            })
            .OrderBy(item => item.Time)
            .ThenBy(item => item.IsNoteOn ? 1 : 0)
            .ThenBy(item => item.KeyIndex)
            .ToArray();
    }

    private static bool IsPlayable(Note note) =>
        note.TargetKeyIndex is >= 0 and < 88 &&
        note.Velocity is >= 0 and <= 127 &&
        double.IsFinite(note.StartTime) && note.StartTime >= 0 &&
        double.IsFinite(note.Duration) && note.Duration > 0;

    public IReadOnlyList<Note> Notes => readOnlyNotes;
    public double TotalDuration { get; }
    public double MaxNoteDuration { get; }
    internal PlaybackEvent[] Events { get; }

    public (int Start, int End) GetVisibleRange(double position, double lookBehind, double lookAhead)
    {
        double minimumStart = position - Math.Max(0, lookBehind) - MaxNoteDuration;
        double maximumStart = position + Math.Max(0, lookAhead);
        return (LowerBound(minimumStart), UpperBound(maximumStart));
    }

    private int LowerBound(double time)
    {
        int low = 0;
        int high = notes.Length;
        while (low < high)
        {
            int middle = low + ((high - low) / 2);
            if (notes[middle].StartTime < time)
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

    private int UpperBound(double time)
    {
        int low = 0;
        int high = notes.Length;
        while (low < high)
        {
            int middle = low + ((high - low) / 2);
            if (notes[middle].StartTime <= time)
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

internal readonly record struct PlaybackEvent(
    double Time,
    int KeyIndex,
    int Velocity,
    bool IsNoteOn);

public sealed class PlaybackController
{
    private readonly PlaybackSession session;
    private readonly IMidiOutput midiOutput;
    private readonly PlaybackClock clock;
    private readonly int[] activePitchCounts = new int[88];
    private int eventCursor;

    public PlaybackController(
        PlaybackSession session,
        IMidiOutput midiOutput,
        PlaybackClock? clock = null)
    {
        this.session = session ?? throw new ArgumentNullException(nameof(session));
        this.midiOutput = midiOutput ?? throw new ArgumentNullException(nameof(midiOutput));
        this.clock = clock ?? new PlaybackClock();
        this.clock.Reset(0, running: true);
    }

    public PlaybackSession Session => session;
    public double Position => Math.Clamp(clock.Position, 0, session.TotalDuration);
    public bool IsPlaying => clock.IsRunning && !IsCompleted;
    public double PlaybackRate => clock.PlaybackRate;
    public bool IsCompleted { get; private set; }
    public bool IsKeyActive(int keyIndex) => keyIndex is >= 0 and < 88 && activePitchCounts[keyIndex] > 0;

    public void Update()
    {
        if (!clock.IsRunning || IsCompleted)
        {
            return;
        }

        double position = clock.Position;
        while (eventCursor < session.Events.Length && session.Events[eventCursor].Time <= position)
        {
            ApplyEvent(session.Events[eventCursor]);
            eventCursor++;
        }

        if (position >= session.TotalDuration)
        {
            clock.Seek(session.TotalDuration);
            clock.Pause();
            Silence();
            IsCompleted = true;
        }
    }

    public void Pause()
    {
        clock.Pause();
        Silence();
    }

    public void Resume()
    {
        if (Position >= session.TotalDuration)
        {
            Seek(0, resume: true);
            return;
        }
        RestoreAt(Position);
        clock.Resume();
        IsCompleted = false;
    }

    public void Seek(double position, bool resume)
    {
        clock.Pause();
        Silence();
        SetSeekPosition(position, resume, alreadySilenced: true);
    }

    public void CommitSilencedSeek(double position, bool resume)
    {
        clock.Pause();
        Array.Clear(activePitchCounts);
        SetSeekPosition(position, resume, alreadySilenced: true);
    }

    private void SetSeekPosition(double position, bool resume, bool alreadySilenced)
    {
        double target = Math.Clamp(position, 0, session.TotalDuration);
        clock.Seek(target);
        eventCursor = UpperBoundEvents(target);
        IsCompleted = target >= session.TotalDuration;
        if (resume && !IsCompleted)
        {
            RestoreAt(target, silenceFirst: !alreadySilenced);
            clock.Resume();
        }
    }

    public void Stop()
    {
        clock.Pause();
        Silence();
    }

    public void SetPlaybackRate(double rate) => clock.SetPlaybackRate(rate);

    private void ApplyEvent(PlaybackEvent item)
    {
        if (item.IsNoteOn)
        {
            activePitchCounts[item.KeyIndex]++;
            if (activePitchCounts[item.KeyIndex] == 1)
            {
                midiOutput.NoteOn(item.KeyIndex + 21, item.Velocity);
            }
            return;
        }

        if (activePitchCounts[item.KeyIndex] <= 0)
        {
            return;
        }
        activePitchCounts[item.KeyIndex]--;
        if (activePitchCounts[item.KeyIndex] == 0)
        {
            midiOutput.NoteOff(item.KeyIndex + 21);
        }
    }

    private void RestoreAt(double position, bool silenceFirst = true)
    {
        if (silenceFirst)
        {
            Silence();
        }
        else
        {
            Array.Clear(activePitchCounts);
        }
        for (int index = 0; index < eventCursor; index++)
        {
            PlaybackEvent item = session.Events[index];
            activePitchCounts[item.KeyIndex] += item.IsNoteOn ? 1 : -1;
            if (activePitchCounts[item.KeyIndex] < 0)
            {
                activePitchCounts[item.KeyIndex] = 0;
            }
        }
        for (int keyIndex = 0; keyIndex < activePitchCounts.Length; keyIndex++)
        {
            if (activePitchCounts[keyIndex] > 0)
            {
                midiOutput.NoteOn(keyIndex + 21, 80);
            }
        }
    }

    private void Silence()
    {
        midiOutput.AllNotesOff();
        Array.Clear(activePitchCounts);
    }

    private int UpperBoundEvents(double time)
    {
        int low = 0;
        int high = session.Events.Length;
        while (low < high)
        {
            int middle = low + ((high - low) / 2);
            if (session.Events[middle].Time <= time)
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

public static class PlaybackFormatting
{
    public static string FormatTime(double seconds)
    {
        long totalSeconds = (long)Math.Floor(Math.Max(0, double.IsFinite(seconds) ? seconds : 0));
        TimeSpan time = TimeSpan.FromSeconds(totalSeconds);
        return totalSeconds >= 3600
            ? $"{(long)time.TotalHours}:{time.Minutes:00}:{time.Seconds:00}"
            : $"{time.Minutes:00}:{time.Seconds:00}";
    }

    public static double PositionFromSlider(float mouseX, float sliderX, float sliderWidth, double duration)
    {
        if (sliderWidth <= 0 || !double.IsFinite(duration) || duration <= 0)
        {
            return 0;
        }
        return Math.Clamp((mouseX - sliderX) / sliderWidth, 0f, 1f) * duration;
    }
}
