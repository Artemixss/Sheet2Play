using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using MeltySynth;
using SynthesiaClone;
using Note = SynthesiaClone.Note;

namespace SfzSpike;

/// <summary>
/// Phase 4a spike: the app's SoundFont piano (YDP) against Salamander through a managed SFZ player.
/// <code>
/// SfzSpike bank      SFZ BANK_DIR
/// SfzSpike render    SFZ BANK_DIR SOUNDFONT OUT_DIR SONG...
/// SfzSpike measure   SFZ BANK_DIR SOUNDFONT OUT_JSON DENSE_SONG
/// </code>
/// A SONG is a library file (a MIDI file) or <c>recent:ENGINE:MANIFEST_RELATIVE_PATH</c> for a song
/// package, so a cached conversion is reopened and never recognized again. Songs play with every
/// expression switch on, as the app plays them by default.
/// </summary>
internal static class Program
{
    private const int SampleRate = 48000;
    private const int BlockFrames = 1024;
    private const double TailSeconds = 3.0;

    private static int Main(string[] args)
    {
        try
        {
            return args.FirstOrDefault() switch
            {
                "bank" => Bank(args[1], args[2]),
                "render" => Render(args[1], args[2], args[3], args[4], args[5..]),
                "measure" => Measure(args[1], args[2], args[3], args[4], args[5]),
                "tones" => Tones(args[1], args[2], args[3], args[4]),
                _ => Usage()
            };
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static int Usage()
    {
        Console.Error.WriteLine("SfzSpike bank|render|measure ... (see Program.cs)");
        return 2;
    }

    // --- bank ----------------------------------------------------------------------------------

    private static int Bank(string sfz, string directory)
    {
        SfzInstrument instrument = new(sfz);
        Stopwatch elapsed = Stopwatch.StartNew();
        BankIndex index = SfzBank.Build(instrument, directory);
        Console.WriteLine($"[BANK] {index.Samples.Count} samples, {index.TotalFrames:N0} frames, " +
            $"{new FileInfo(Path.Combine(directory, SfzBank.BankName)).Length / 1e6:F0} MB in {elapsed.Elapsed.TotalSeconds:F1} s");
        return 0;
    }

    // --- render --------------------------------------------------------------------------------

    private static int Render(string sfz, string bankDirectory, string soundFontPath, string outputDirectory, string[] songs)
    {
        Directory.CreateDirectory(outputDirectory);
        SfzInstrument instrument = new(sfz);
        using SfzBank bank = SfzBank.Open(bankDirectory, instrument);
        SoundFont soundFont = new(soundFontPath);
        List<object> rows = [];
        foreach (string song in songs)
        {
            (string name, PlaybackSession session) = LoadSession(song);
            double seconds = session.TotalDuration + TailSeconds;
            float[] ydp = RenderYdp(soundFont, session, seconds);
            float[] dry = RenderSfz(instrument, bank, session, seconds, reverb: false);
            float[] wet = RenderSfz(instrument, bank, session, seconds, reverb: true);
            // Matched to the app's loudness, because the louder of two renders tends to sound better.
            double target = Rms(ydp);
            float dryScale = (float)(target / Rms(dry));
            float wetScale = (float)(target / Rms(wet));
            string safe = string.Join("_", name.Split(Path.GetInvalidFileNameChars()));
            WriteWav(Path.Combine(outputDirectory, $"{safe} - 1 YDP (app today).wav"), ydp, 1f);
            WriteWav(Path.Combine(outputDirectory, $"{safe} - 2 Salamander.wav"), wet, wetScale);
            WriteWav(Path.Combine(outputDirectory, $"{safe} - 3 Salamander dry.wav"), dry, dryScale);
            rows.Add(new
            {
                song = name,
                notes = session.Notes.Count,
                pedalChanges = session.Pedal.Count,
                seconds = Math.Round(seconds, 1),
                ydpPeak = Math.Round(Peak(ydp), 3),
                salamanderPeak = Math.Round(Peak(wet) * wetScale, 3),
                salamanderScale = Math.Round(wetScale, 3),
                salamanderDryScale = Math.Round(dryScale, 3)
            });
            Console.WriteLine($"[RENDER] {name}: {session.Notes.Count} notes, {session.Pedal.Count} pedal changes, " +
                $"peaks YDP {Peak(ydp):F3} Salamander {Peak(wet) * wetScale:F3}");
        }
        File.WriteAllText(Path.Combine(outputDirectory, "renders.json"),
            JsonSerializer.Serialize(rows, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }

    private static (string Name, PlaybackSession Session) LoadSession(string song)
    {
        SongLoadResult loaded;
        if (song.StartsWith("recent:", StringComparison.Ordinal))
        {
            string[] parts = song.Split(':', 3);
            OmrEngine engine = Enum.Parse<OmrEngine>(parts[1], ignoreCase: true);
            loaded = SongCache.LoadRecent(new RecentSongEntry(parts[2], "Spike", engine, DateTimeOffset.MinValue),
                recordRecent: false);
        }
        else
        {
            loaded = SongCache.LoadOrCreateDetailed(song, OmrEngine.DirectMidi, recordRecent: false);
        }
        SongPlayback playback = ExpressionPlayback.ForSong(loaded, new ExpressionOptions());
        string name = loaded.DisplayName == "Spike" ? Path.GetFileName(Path.GetDirectoryName(song))! : loaded.DisplayName;
        return (name, new PlaybackSession(playback.Notes, pedal: playback.Pedal));
    }

    private static float[] RenderYdp(SoundFont soundFont, PlaybackSession session, double seconds, double rate = 1.0)
    {
        CaptureSink capture = new(BlockFrames);
        OneBlockSink sink = new(capture);
        SoundFontEngine engine = new(soundFont, sink, session, SampleRate);
        engine.SetRate(rate);
        engine.Seek(0);
        engine.Start();
        while (engine.SubmittedSongSeconds < seconds)
        {
            sink.Arm();
            engine.Pump();
        }
        return capture.ToArray();
    }

    private static float[] RenderSfz(SfzInstrument instrument, SfzBank bank, PlaybackSession session, double seconds,
        bool reverb, double rate = 1.0)
    {
        CaptureSink capture = new(BlockFrames);
        SfzSynth synth = new(instrument, bank, capture, session, SampleRate, reverb, masterGain: 0.5f) { Rate = rate };
        while (synth.SubmittedSongSeconds < seconds)
        {
            synth.RenderBlock();
        }
        return capture.ToArray();
    }

    // --- tones ---------------------------------------------------------------------------------

    /// <summary>
    /// Single notes two seconds apart for an objective check: pitch across the keyboard (every key,
    /// so the resampled neighbours of each sample are included) and loudness across velocity.
    /// </summary>
    private static int Tones(string sfz, string bankDirectory, string soundFontPath, string outputDirectory)
    {
        Directory.CreateDirectory(outputDirectory);
        SfzInstrument instrument = new(sfz);
        using SfzBank bank = SfzBank.Open(bankDirectory, instrument);
        SoundFont soundFont = new(soundFontPath);
        List<Note> pitch = [];
        int[] keys = [21, 22, 23, 33, 44, 45, 46, 47, 48, 57, 58, 59, 60, 61, 62, 69, 70, 71, 72, 81, 82, 83, 84, 96, 100, 105, 108];
        for (int index = 0; index < keys.Length; index++)
        {
            pitch.Add(new Note(keys[index] - 21, index * 2.0, 1.5, 80, Raylib_cs.Color.SkyBlue));
        }
        List<Note> loudness = [];
        int[] velocities = [10, 30, 50, 70, 90, 110, 127];
        for (int index = 0; index < velocities.Length; index++)
        {
            loudness.Add(new Note(60 - 21, index * 2.0, 1.5, velocities[index], Raylib_cs.Color.SkyBlue));
        }
        foreach ((string name, List<Note> notes) in new[] { ("pitch", pitch), ("velocity", loudness) })
        {
            PlaybackSession session = new(notes);
            double seconds = session.TotalDuration + 1;
            WriteWav(Path.Combine(outputDirectory, $"{name}-salamander.wav"), RenderSfz(instrument, bank, session, seconds, reverb: false), 1f);
            WriteWav(Path.Combine(outputDirectory, $"{name}-ydp.wav"), RenderYdp(soundFont, session, seconds), 1f);
        }
        File.WriteAllText(Path.Combine(outputDirectory, "tones.json"), JsonSerializer.Serialize(new { keys, velocities, spacingSeconds = 2.0 }));
        return 0;
    }

    // --- measure -------------------------------------------------------------------------------

    private static int Measure(string sfz, string bankDirectory, string soundFontPath, string output, string denseSong)
    {
        Process self = Process.GetCurrentProcess();
        (long privateBefore, long workingBefore) = Memory(self);

        Stopwatch watch = Stopwatch.StartNew();
        SoundFont soundFont = new(soundFontPath);
        double ydpLoad = watch.Elapsed.TotalSeconds;
        (long privateYdp, long workingYdp) = Memory(self);

        watch.Restart();
        SfzInstrument instrument = new(sfz);
        using SfzBank bank = SfzBank.Open(bankDirectory, instrument);
        bank.Prefetch(SampleRate / 2);
        double sfzLoad = watch.Elapsed.TotalSeconds;
        (long privateSfz, long workingSfz) = Memory(self);

        (string denseName, PlaybackSession dense) = LoadSession(denseSong);
        var timing = new List<object>();
        foreach (double rate in new[] { 1.0, 2.0 })
        {
            // Ten minutes of audio: the song repeated as often as that takes at this rate.
            PlaybackSession longSession = Repeat(dense, 600 * rate);
            timing.Add(TimeBlocks("YDP", rate, longSession, sink => new YdpBlocks(soundFont, sink, longSession, rate)));
            timing.Add(TimeBlocks("Salamander", rate, longSession,
                sink => new SfzBlocks(new SfzSynth(instrument, bank, sink, longSession, SampleRate, reverb: true, 0.5f) { Rate = rate })));
        }
        (long privateAfter, long workingAfter) = Memory(self);

        PlaybackSession stress = Stress();
        var stressTiming = new[]
        {
            TimeBlocks("YDP", 1.0, stress, sink => new YdpBlocks(soundFont, sink, stress, 1.0), voicesFrom: 4.0),
            TimeBlocks("Salamander", 1.0, stress,
                sink => new SfzBlocks(new SfzSynth(instrument, bank, sink, stress, SampleRate, reverb: true, 0.5f)), voicesFrom: 4.0)
        };

        (_, PlaybackSession sample) = LoadSession(denseSong);
        string first = Hash(RenderSfz(instrument, bank, sample, 20, reverb: true));
        string second = Hash(RenderSfz(instrument, bank, sample, 20, reverb: true));

        int occurrences = instrument.Opcodes.Values.Sum();
        int covered = instrument.Opcodes.Where(pair => SfzInstrument.Supported.Contains(pair.Key)).Sum(pair => pair.Value);
        var report = new
        {
            plan = "2026-10-19-musicxml-songs",
            phase = "4a",
            sampleRate = SampleRate,
            blockFrames = BlockFrames,
            blockBudgetMs = Math.Round(1000.0 * BlockFrames / SampleRate, 2),
            memory = new
            {
                privateBytesBeforeMb = Mb(privateBefore),
                ydpPrivateRiseMb = Mb(privateYdp - privateBefore),
                ydpWorkingSetRiseMb = Mb(workingYdp - workingBefore),
                salamanderPrivateRiseMb = Mb(privateSfz - privateYdp),
                salamanderWorkingSetRiseMb = Mb(workingSfz - workingYdp),
                privateBytesAfterTenMinuteRendersMb = Mb(privateAfter),
                workingSetAfterTenMinuteRendersMb = Mb(workingAfter),
                bankFileMb = Mb(new FileInfo(Path.Combine(bankDirectory, SfzBank.BankName)).Length)
            },
            loadSeconds = new { ydp = Math.Round(ydpLoad, 2), salamanderWarm = Math.Round(sfzLoad, 2) },
            denseSong = new { name = denseName, notes = dense.Notes.Count, seconds = Math.Round(dense.TotalDuration, 1) },
            tenMinuteRenders = timing,
            stress256 = stressTiming,
            deterministic = first == second,
            coverage = new
            {
                opcodes = instrument.Opcodes.OrderByDescending(pair => pair.Value).ToDictionary(pair => pair.Key, pair => pair.Value),
                unsupported = instrument.Opcodes.Keys.Where(key => !SfzInstrument.Supported.Contains(key)).ToArray(),
                unknownHeaders = instrument.UnknownHeaders,
                coveredOccurrencesPercent = Math.Round(100.0 * covered / occurrences, 2),
                regions = instrument.Regions.Count
            }
        };
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output))!);
        File.WriteAllText(output, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine(JsonSerializer.Serialize(new { report.memory, report.loadSeconds, report.deterministic }));
        return 0;
    }

    private interface IBlocks
    {
        void Render();
        int Voices { get; }
    }

    private sealed class YdpBlocks : IBlocks
    {
        private readonly SoundFontEngine engine;
        private readonly OneBlockSink sink;

        public YdpBlocks(SoundFont soundFont, IAudioSink target, PlaybackSession session, double rate)
        {
            sink = new OneBlockSink(target);
            engine = new SoundFontEngine(soundFont, sink, session, SampleRate);
            engine.SetRate(rate);
            engine.Seek(0);
            engine.Start();
        }

        public void Render()
        {
            sink.Arm();
            engine.Pump();
        }

        public int Voices => engine.ActiveVoiceCount;
    }

    private sealed class SfzBlocks(SfzSynth synth) : IBlocks
    {
        public void Render() => synth.RenderBlock();
        public int Voices => synth.ActiveVoiceCount;
        public SfzSynth Synth => synth;
    }

    /// <summary>
    /// Times every block against its real-time budget. A block slower than its own length is one the
    /// app's two-buffer stream could not have had ready: a dropout.
    /// </summary>
    private static object TimeBlocks(string piano, double rate, PlaybackSession session, Func<IAudioSink, IBlocks> create,
        double voicesFrom = 0)
    {
        NullSink sink = new(BlockFrames);
        IBlocks blocks = create(sink);
        double budget = (double)BlockFrames / SampleRate;
        int count = (int)Math.Ceiling(Math.Min(600, (session.TotalDuration + TailSeconds) / rate) / budget);
        List<double> times = new(count);
        int late = 0, peakVoices = 0;
        long started = Stopwatch.GetTimestamp();
        for (int block = 0; block < count; block++)
        {
            long before = Stopwatch.GetTimestamp();
            blocks.Render();
            double seconds = Stopwatch.GetElapsedTime(before).TotalSeconds;
            peakVoices = Math.Max(peakVoices, blocks.Voices);
            if (block * budget >= voicesFrom)
            {
                times.Add(seconds);
                late += seconds > budget ? 1 : 0;
            }
        }
        double total = Stopwatch.GetElapsedTime(started).TotalSeconds;
        times.Sort();
        return new
        {
            piano,
            rate,
            audioSeconds = Math.Round(count * budget, 1),
            measuredBlocks = times.Count,
            lateBlocks = late,
            cpuPercentOfRealTime = Math.Round(100 * total / (count * budget), 2),
            medianBlockMs = Math.Round(times[times.Count / 2] * 1000, 3),
            p99BlockMs = Math.Round(times[(int)(times.Count * 0.99)] * 1000, 3),
            maxBlockMs = Math.Round(times[^1] * 1000, 3),
            peakVoices,
            stolenVoices = (blocks as SfzBlocks)?.Synth.StolenVoices
        };
    }

    /// <summary>The song played back to back until it lasts <paramref name="seconds"/> of song time.</summary>
    private static PlaybackSession Repeat(PlaybackSession session, double seconds)
    {
        double period = session.TotalDuration + 1.0;
        int copies = (int)Math.Ceiling(seconds / period);
        List<Note> notes = [];
        List<PedalChange> pedal = [];
        for (int copy = 0; copy < copies; copy++)
        {
            double shift = copy * period;
            notes.AddRange(session.Notes.Select(note => note with { StartTime = note.StartTime + shift }));
            pedal.AddRange(session.Pedal.Select(change => change with { Time = change.Time + shift }));
            pedal.Add(new PedalChange(shift + session.TotalDuration + 0.5, 0));
        }
        return new PlaybackSession(notes, pedal: pedal);
    }

    /// <summary>Pedal down, then every key struck three times in four seconds: past 256 voices.</summary>
    private static PlaybackSession Stress()
    {
        List<Note> notes = [];
        int[] velocities = [40, 80, 120];
        for (int pass = 0; pass < velocities.Length; pass++)
        {
            for (int key = 0; key < 88; key++)
            {
                double start = pass * 1.2 + key * 0.012;
                notes.Add(new Note(key, start, 0.2, velocities[pass], Raylib_cs.Color.SkyBlue));
            }
        }
        notes.Add(new Note(40, 9.0, 0.1, 64, Raylib_cs.Color.SkyBlue));
        return new PlaybackSession(notes, pedal: [new PedalChange(0, 127), new PedalChange(9.5, 0)]);
    }

    // --- helpers -------------------------------------------------------------------------------

    private static (long Private, long Working) Memory(Process process)
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        process.Refresh();
        return (process.PrivateMemorySize64, process.WorkingSet64);
    }

    private static double Mb(long bytes) => Math.Round(bytes / 1048576.0, 1);

    private static double Rms(float[] samples)
    {
        double sum = 0;
        foreach (float sample in samples)
        {
            sum += sample * (double)sample;
        }
        return Math.Sqrt(sum / Math.Max(1, samples.Length));
    }

    private static float Peak(float[] samples) => samples.Length == 0 ? 0 : samples.Max(Math.Abs);

    private static string Hash(float[] samples)
    {
        byte[] bytes = new byte[samples.Length * 4];
        Buffer.BlockCopy(samples, 0, bytes, 0, bytes.Length);
        return Convert.ToHexStringLower(SHA256.HashData(bytes));
    }

    private static void WriteWav(string path, float[] samples, float scale)
    {
        using WavFileSink sink = new(path, SampleRate, BlockFrames);
        float[] block = new float[BlockFrames * 2];
        for (int start = 0; start + block.Length <= samples.Length; start += block.Length)
        {
            for (int index = 0; index < block.Length; index++)
            {
                block[index] = Math.Clamp(samples[start + index] * scale, -1f, 1f);
            }
            sink.Submit(block);
        }
    }

    private sealed class CaptureSink(int blockFrames) : IAudioSink
    {
        private readonly List<float> samples = [];
        public int BlockFrames => blockFrames;
        public bool WantsBlock => true;
        public void Submit(ReadOnlySpan<float> interleaved) => samples.AddRange(interleaved);
        public float[] ToArray() => samples.ToArray();
    }

    private sealed class NullSink(int blockFrames) : IAudioSink
    {
        public int BlockFrames => blockFrames;
        public bool WantsBlock => true;
        public void Submit(ReadOnlySpan<float> interleaved)
        {
        }
    }

    /// <summary>Lets <see cref="SoundFontEngine.Pump"/> render exactly one block per call.</summary>
    private sealed class OneBlockSink(IAudioSink target) : IAudioSink
    {
        private bool armed;
        public int BlockFrames => target.BlockFrames;
        public bool WantsBlock => armed;
        public void Arm() => armed = true;

        public void Submit(ReadOnlySpan<float> interleaved)
        {
            armed = false;
            target.Submit(interleaved);
        }
    }
}
