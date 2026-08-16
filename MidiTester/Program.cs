using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SynthesiaClone;

// Diagnostic + smoke harness: reports the library exactly as the app sees it, then
// verifies every MIDI file parses and builds a playback session.
// Run with: dotnet run --project MidiTester
class Program
{
    static void Main()
    {
        string home = SongCache.ApplicationDirectory;
        Console.WriteLine("=== Library resolution ===");
        Console.WriteLine($"  SHEET2PLAY_HOME : {Environment.GetEnvironmentVariable("SHEET2PLAY_HOME") ?? "(not set)"}");
        Console.WriteLine($"  ApplicationDirectory: {home}");

        string songs = Path.Combine(home, "songs");
        foreach (string rel in new[] { "pdf", "midi\\custom", "midi\\homr", "midi\\zeus" })
        {
            string full = Path.Combine(songs, rel);
            int count = Directory.Exists(full) ? Directory.GetFiles(full).Length : -1;
            Console.WriteLine(count < 0
                ? $"  songs\\{rel,-12} MISSING  {full}"
                : $"  songs\\{rel,-12} {count,3} files on disk");
        }

        Console.WriteLine("\n=== What the app's own API returns ===");
        Console.WriteLine($"  GetPdfLibrary()  : {SongCache.GetPdfLibrary().Count}");
        Console.WriteLine($"  GetMidiLibrary() : {SongCache.GetMidiLibrary().Count}");
        Console.WriteLine($"  GetCachedSongs() : {SongCache.GetCachedSongs().Count}");

        string dir = Path.Combine(home, "songs", "midi", "custom");
        if (!Directory.Exists(dir))
        {
            Console.WriteLine($"\nNot found: {dir}");
            return;
        }

        string[] files = Directory.GetFiles(dir)
            .Where(f => f.EndsWith(".mid", StringComparison.OrdinalIgnoreCase)
                     || f.EndsWith(".midi", StringComparison.OrdinalIgnoreCase))
            .OrderBy(f => f)
            .ToArray();

        Console.WriteLine($"\n=== Parsing {files.Length} MIDI files ===");
        int ok = 0, failed = 0;
        foreach (string path in files)
        {
            string name = Path.GetFileName(path);
            try
            {
                SongLoadResult result = SongCache.LoadOrCreateDetailed(path, OmrEngine.DirectMidi);
                PlaybackSession session = new(result.Notes);
                Console.WriteLine($"  OK    {name}  ({result.Notes.Count} notes, {session.TotalDuration:F1}s)");
                ok++;
            }
            catch (Exception exception)
            {
                Console.WriteLine($"  FAIL  {name}: {exception.GetType().Name}: {exception.Message}");
                failed++;
            }
        }

        Console.WriteLine($"\n=== {ok} passed, {failed} failed ===");
    }
}
