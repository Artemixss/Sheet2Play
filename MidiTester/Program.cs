using System;
using System.IO;
using System.Linq;
using SynthesiaClone;

// Smoke test: every MIDI file in songs/midi/custom must parse and build a
// playback session without throwing. Run with: dotnet run --project MidiTester
class Program
{
    static void Main()
    {
        // Resolve through SongCache so this always tests the same library the app uses,
        // wherever that is (%APPDATA%\Sheet2Play by default).
        string dir = Path.Combine(
            SongCache.ApplicationDirectory, "songs", "midi", "custom");

        if (!Directory.Exists(dir))
        {
            Console.WriteLine($"Not found: {dir}");
            return;
        }

        string[] files = Directory.GetFiles(dir)
            .Where(f => f.EndsWith(".mid", StringComparison.OrdinalIgnoreCase)
                     || f.EndsWith(".midi", StringComparison.OrdinalIgnoreCase))
            .OrderBy(f => f)
            .ToArray();

        Console.WriteLine($"Testing {files.Length} MIDI files\n");

        int ok = 0, failed = 0;
        foreach (string path in files)
        {
            string name = Path.GetFileName(path);
            try
            {
                SongLoadResult result = SongCache.LoadOrCreateDetailed(path, OmrEngine.DirectMidi);

                int bad = result.Notes.Count(note =>
                    note.TargetKeyIndex is < 0 or >= 88 || note.Velocity is < 0 or > 127 ||
                    !double.IsFinite(note.StartTime) || note.StartTime < 0 ||
                    !double.IsFinite(note.Duration) || note.Duration <= 0);

                PlaybackSession session = new(result.Notes);

                Console.WriteLine($"  OK    {name}");
                Console.WriteLine($"          notes={result.Notes.Count} invalid={bad} " +
                                  $"duration={session.TotalDuration:F1}s");
                ok++;
            }
            catch (Exception exception)
            {
                Console.WriteLine($"  FAIL  {name}");
                Console.WriteLine($"          {exception.GetType().Name}: {exception.Message}");
                failed++;
            }
        }

        Console.WriteLine($"\n=== {ok} passed, {failed} failed ===");
    }
}
