using System.Text.Json;
using Melanchall.DryWetMidi.Common;
using Melanchall.DryWetMidi.Core;
using VisualNote = SynthesiaClone.Note;

namespace SynthesiaClone;

/// <summary>
/// What the playback screen's Export MIDI, Export MusicXML and Re-convert buttons need from the
/// library (<c>plans/2026-10-19-musicxml-songs.md</c>, Phase 5).
/// </summary>
public static partial class SongCache
{
    /// <summary>Exported files play at this tempo, so two beats are exactly one second.</summary>
    private const double ExportTicksPerSecond = TicksPerQuarterNote * 2.0;

    private const int ExportMicrosecondsPerQuarter = 500_000;

    /// <summary>
    /// The combined MusicXML a song package plays from, or null for a song without a score: a
    /// MIDI file, a legacy MIDI cache, or a Zeus conversion.
    /// </summary>
    public static string? ScorePath(SongLoadResult song) =>
        ScorePath(song, ApplicationDirectory);

    internal static string? ScorePath(SongLoadResult song, string applicationDirectory)
    {
        ArgumentNullException.ThrowIfNull(song);
        if (song.Performance is null || song.ManifestRelativePath is not string manifest ||
            !manifest.EndsWith(InterpretationManifestName, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }
        string path = Path.Combine(applicationDirectory, Path.GetDirectoryName(manifest)!, CombinedScoreName);
        return File.Exists(path) ? path : null;
    }

    /// <summary>
    /// Writes what is playing as a standard MIDI file: the notes with the velocities and sounding
    /// lengths the player uses, and the sustain pedal on every channel they occupy.
    /// </summary>
    /// <remarks>
    /// An export, not a cache: nothing reads it back. Song time is already in seconds, after the
    /// score's tempo marks, so the file carries one tempo and keeps the timing exactly. A note that
    /// overlaps another of the same pitch goes on the next free channel, as the MIDI cache does,
    /// so neither loses its end.
    /// </remarks>
    public static void ExportMidi(string outputPath, IReadOnlyList<VisualNote> notes, IReadOnlyList<PedalChange> pedal)
    {
        ArgumentNullException.ThrowIfNull(notes);
        ArgumentNullException.ThrowIfNull(pedal);
        List<ScheduledEvent> scheduled = new(notes.Count * 2 + pedal.Count + 1)
        {
            new ScheduledEvent(0, 0, new SetTempoEvent(ExportMicrosecondsPerQuarter))
        };
        Dictionary<int, long[]> channelEndTicksByPitch = [];
        int channels = 1;
        foreach (VisualNote note in notes
                     .OrderBy(static note => note.StartTime)
                     .ThenBy(static note => note.TargetKeyIndex))
        {
            long startTick = ExportTick(note.StartTime);
            long endTick = Math.Max(startTick + 1, ExportTick(note.EndTime));
            int channel = AllocateChannel(channelEndTicksByPitch, note.MidiPitch, startTick, endTick);
            channels = Math.Max(channels, channel + 1);
            FourBitNumber midiChannel = (FourBitNumber)(byte)channel;
            // At one tick a note ends before the next starts, so a repeated key is struck again.
            scheduled.Add(new ScheduledEvent(endTick, 2, new NoteOffEvent(
                (SevenBitNumber)(byte)note.MidiPitch, (SevenBitNumber)(byte)0) { Channel = midiChannel }));
            scheduled.Add(new ScheduledEvent(startTick, 3, new NoteOnEvent(
                (SevenBitNumber)(byte)note.MidiPitch, (SevenBitNumber)(byte)Math.Clamp(note.Velocity, 1, 127))
            {
                Channel = midiChannel
            }));
        }
        foreach (PedalChange change in pedal)
        {
            // Released before the notes at the same tick and pressed after them, as the player does,
            // so a change at a chord catches that chord and not the one before.
            int priority = change.Value >= SongOverlay.PedalDownValue ? 4 : 1;
            for (int channel = 0; channel < channels; channel++)
            {
                scheduled.Add(new ScheduledEvent(ExportTick(change.Time), priority, new ControlChangeEvent(
                    (SevenBitNumber)(byte)64, (SevenBitNumber)(byte)Math.Clamp(change.Value, 0, 127))
                {
                    Channel = (FourBitNumber)(byte)channel
                }));
            }
        }
        scheduled.Sort(static (left, right) =>
        {
            int timeComparison = left.Time.CompareTo(right.Time);
            return timeComparison != 0 ? timeComparison : left.Priority.CompareTo(right.Priority);
        });

        TrackChunk track = new();
        long previousTick = 0;
        foreach (ScheduledEvent scheduledEvent in scheduled)
        {
            scheduledEvent.Event.DeltaTime = scheduledEvent.Time - previousTick;
            track.Events.Add(scheduledEvent.Event);
            previousTick = scheduledEvent.Time;
        }
        MidiFile file = new(track) { TimeDivision = new TicksPerQuarterNoteTimeDivision(TicksPerQuarterNote) };
        WriteAtomically(outputPath, temporary => file.Write(temporary, overwriteFile: true));
    }

    /// <summary>Copies a song's MusicXML to <paramref name="outputPath"/>, replacing an earlier export.</summary>
    public static void ExportMusicXml(SongLoadResult song, string outputPath)
    {
        string source = ScorePath(song)
            ?? throw new InvalidOperationException("This song has no score to export; it was not read from MusicXML.");
        WriteAtomically(outputPath, temporary => File.Copy(source, temporary, overwrite: true));
    }

    /// <summary>
    /// The library file a song was converted from, found by the hash its package or cache recorded;
    /// null when it is no longer in <c>songs/pdf</c> or the song was not converted from one.
    /// </summary>
    /// <remarks>
    /// Files whose name the conversion would have kept it under are hashed first, so the usual case
    /// reads one file. Only when that fails is every library file hashed.
    /// </remarks>
    public static string? FindSource(SongLoadResult song) =>
        FindSource(song, ApplicationDirectory, GetPdfLibrary().Select(static entry => entry.FullPath).ToArray());

    internal static string? FindSource(SongLoadResult song, string applicationDirectory, IReadOnlyList<string> library)
    {
        ArgumentNullException.ThrowIfNull(song);
        if (!OmrEngines.RunsOmr(song.Engine) || song.ManifestRelativePath is not string relative)
        {
            return null;
        }
        string manifest = Path.Combine(applicationDirectory, relative);
        // A package's interpretation sits two folders below the package, whose song.json has the hash.
        string recordPath = manifest.EndsWith(InterpretationManifestName, StringComparison.OrdinalIgnoreCase)
            ? Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(manifest)!)!)!,
                PackageManifestName)
            : manifest;
        if (ReadSourceHash(recordPath) is not string sourceHash)
        {
            return null;
        }

        string cacheName = Path.GetFileName(manifest);
        cacheName = cacheName.EndsWith(".mid.cache.json", StringComparison.OrdinalIgnoreCase)
            ? cacheName[..^".mid.cache.json".Length]
            : "";
        int timing = cacheName.IndexOf(".timing-", StringComparison.Ordinal);
        if (timing >= 0)
        {
            cacheName = cacheName[..timing];
        }
        bool Likely(string path)
        {
            string name = Path.GetFileNameWithoutExtension(path);
            return name.StartsWith(sourceHash, StringComparison.OrdinalIgnoreCase) ||
                (cacheName.Length > 0 && string.Equals(name, cacheName, StringComparison.OrdinalIgnoreCase));
        }
        foreach (string candidate in library.Where(Likely).Concat(library.Where(path => !Likely(path))))
        {
            try
            {
                if (string.Equals(ComputeSha256(candidate), sourceHash, StringComparison.OrdinalIgnoreCase))
                {
                    return candidate;
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                Console.Error.WriteLine($"[SONG CACHE] Could not hash {candidate}: {exception.Message}");
            }
        }
        return null;
    }

    /// <summary>A file's SHA-256 as the library keys songs by it, for tools outside this class.</summary>
    public static string Sha256OfFile(string path) => ComputeSha256(path);

    private static string? ReadSourceHash(string recordPath)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(recordPath));
            return document.RootElement.TryGetProperty("source_sha256", out JsonElement hash) &&
                hash.ValueKind == JsonValueKind.String
                    ? hash.GetString()
                    : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"[SONG CACHE] Could not read the source of {recordPath}: {exception.Message}");
            return null;
        }
    }

    private static long ExportTick(double seconds) => (long)Math.Round(Math.Max(0, seconds) * ExportTicksPerSecond);

    /// <summary>Writes beside the target and moves it into place, so a failed export leaves no half file.</summary>
    private static void WriteAtomically(string outputPath, Action<string> write)
    {
        string directory = Path.GetDirectoryName(Path.GetFullPath(outputPath))!;
        Directory.CreateDirectory(directory);
        string temporary = Path.Combine(directory, $".{Path.GetFileName(outputPath)}.{Guid.NewGuid():N}.tmp");
        try
        {
            write(temporary);
            File.Move(temporary, outputPath, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporary))
            {
                File.Delete(temporary);
            }
        }
    }
}
