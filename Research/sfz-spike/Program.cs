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
/// SfzSpike sfizz     SFIZZ_DLL SFZ BANK_DIR SOUNDFONT OUT_JSON LISTEN_DIR DENSE_SONG SONG...
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

    /// <summary>Length of each timing run; SFZSPIKE_RUN_SECONDS shortens it for a smoke test.</summary>
    private static readonly double RunSeconds =
        double.TryParse(Environment.GetEnvironmentVariable("SFZSPIKE_RUN_SECONDS"), out double seconds) ? seconds : 600;

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
                "sfizz" => CompareSfizz(args[1], args[2], args[3], args[4], args[5], args[6], args[7], args[8..]),
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
            PlaybackSession longSession = Repeat(dense, RunSeconds * rate);
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

    // --- sfizz --------------------------------------------------------------------------------

    /// <summary>
    /// sfizz on the same measurements as <see cref="Measure"/>, with the managed player rerun beside it
    /// so both are timed on the same day. sfizz streams samples from disk on its own threads, so its
    /// timing runs are paced in real time: unpaced, the disk would fall behind and the blocks would be
    /// cheap for the wrong reason. Renders use freewheeling, in which sfizz waits for the disk.
    /// </summary>
    private static int CompareSfizz(string library, string sfz, string bankDirectory, string soundFontPath, string output,
        string listenDirectory, string denseSong, string[] songs)
    {
        Sfizz.UseLibrary(library);
        timeBeginPeriod(1);
        Process self = Process.GetCurrentProcess();
        (string denseName, PlaybackSession dense) = LoadSession(denseSong);
        (long privateBefore, long workingBefore) = Memory(self);

        Stopwatch watch = Stopwatch.StartNew();
        object load;
        var sfizzTiming = new List<object>();
        float[] streamed;
        using (Sfizz live = new(sfz, SampleRate, BlockFrames, freewheeling: false))
        {
            double loadSeconds = watch.Elapsed.TotalSeconds;
            (long privateLoaded, long workingLoaded) = Memory(self);
            Thread.Sleep(2000);
            (long privateSettled, long workingSettled) = Memory(self);
            load = new
            {
                seconds = Math.Round(loadSeconds, 2),
                privateRiseMb = Mb(privateLoaded - privateBefore),
                workingSetRiseMb = Mb(workingLoaded - workingBefore),
                privateRiseAfterTwoSecondsMb = Mb(privateSettled - privateBefore),
                workingSetRiseAfterTwoSecondsMb = Mb(workingSettled - workingBefore),
                liveSampleQuality = live.LiveQuality,
                preloadFrames = live.PreloadFrames,
                preloadedSamples = live.PreloadedSamples,
                regions = live.Regions,
                unknownOpcodes = live.UnknownOpcodes
            };
            Console.WriteLine($"[SFIZZ] loaded: {JsonSerializer.Serialize(load)}");

            // The first pass of the song at 1.0x is kept, to check against a render that waited for the disk.
            int streamedSamples = (int)(dense.TotalDuration * SampleRate) * 2;
            CaptureFirstSink firstPass = new(BlockFrames, streamedSamples);
            foreach (double rate in new[] { 1.0, 2.0 })
            {
                PlaybackSession longSession = Repeat(dense, RunSeconds * rate);
                sfizzTiming.Add(TimeBlocks("sfizz", rate, longSession,
                    sink => new SfizzBlocks(live, new SfizzPlayer(live, rate == 1.0 ? new TeeSink(sink, firstPass) : sink,
                        longSession, SampleRate, 0.5f) { Rate = rate }), paced: true));
                Console.WriteLine($"[SFIZZ] {JsonSerializer.Serialize(sfizzTiming[^1])}");
            }
            (long privateAfter, _) = Memory(self);
            sfizzTiming.Add(new { privateRiseAfterTenMinuteRunsMb = Mb(privateAfter - privateBefore) });
            PlaybackSession stress = Stress();
            sfizzTiming.Add(TimeBlocks("sfizz", 1.0, stress,
                sink => new SfizzBlocks(live, new SfizzPlayer(live, sink, stress, SampleRate, 0.5f)), voicesFrom: 4.0, paced: true));
            Console.WriteLine($"[SFIZZ] stress {JsonSerializer.Serialize(sfizzTiming[^1])}");
            streamed = firstPass.ToArray();
        }

        // The managed player on the same day and the same session, as Measure times it.
        SfzInstrument instrument = new(sfz);
        using SfzBank bank = SfzBank.Open(bankDirectory, instrument);
        bank.Prefetch(SampleRate / 2);
        var managedTiming = new List<object>();
        foreach (double rate in new[] { 1.0, 2.0 })
        {
            PlaybackSession longSession = Repeat(dense, RunSeconds * rate);
            managedTiming.Add(TimeBlocks("Salamander (managed)", rate, longSession,
                sink => new SfzBlocks(new SfzSynth(instrument, bank, sink, longSession, SampleRate, reverb: false, 0.5f) { Rate = rate })));
            Console.WriteLine($"[MANAGED] {JsonSerializer.Serialize(managedTiming[^1])}");
        }

        using Sfizz offline = new(sfz, SampleRate, BlockFrames, freewheeling: true);
        float[] waited = RenderSfizz(offline, dense, dense.TotalDuration);
        string first = Hash(RenderSfizz(offline, dense, 20));
        string second = Hash(RenderSfizz(offline, dense, 20));

        Directory.CreateDirectory(listenDirectory);
        SoundFont soundFont = new(soundFontPath);
        var renders = new List<object>();
        foreach (string song in songs)
        {
            (string name, PlaybackSession session) = LoadSession(song);
            double seconds = session.TotalDuration + TailSeconds;
            float[] ydp = RenderYdp(soundFont, session, seconds);
            float[] managed = RenderSfz(instrument, bank, session, seconds, reverb: false);
            float[] sfizz = RenderSfizz(offline, session, seconds);
            double target = Rms(ydp);
            float managedScale = (float)(target / Rms(managed));
            float sfizzScale = (float)(target / Rms(sfizz));
            string safe = string.Join("_", name.Split(Path.GetInvalidFileNameChars()));
            WriteWav(Path.Combine(listenDirectory, $"{safe} - 4 Salamander sfizz.wav"), sfizz, sfizzScale);
            renders.Add(new
            {
                song = name,
                notes = session.Notes.Count,
                seconds = Math.Round(seconds, 1),
                sfizzPeak = Math.Round(Peak(sfizz) * sfizzScale, 3),
                managedPeak = Math.Round(Peak(managed) * managedScale, 3),
                sfizzToManagedLevelDb = Math.Round(20 * Math.Log10(Rms(sfizz) / Rms(managed)), 2),
                comparison = Compare(managed, managedScale, sfizz, sfizzScale)
            });
            Console.WriteLine($"[RENDER] {JsonSerializer.Serialize(renders[^1])}");
        }

        int compared = Math.Min(streamed.Length, waited.Length);
        var report = new
        {
            plan = "2026-10-19-musicxml-songs",
            phase = "4a",
            sfizz = "1.2.3 win64 release, sfizz.dll through its C API",
            sampleRate = SampleRate,
            blockFrames = BlockFrames,
            blockBudgetMs = Math.Round(1000.0 * BlockFrames / SampleRate, 2),
            load,
            denseSong = new { name = denseName, notes = dense.Notes.Count, seconds = Math.Round(dense.TotalDuration, 1) },
            sfizzPacedRuns = sfizzTiming,
            managedRunsSameDay = managedTiming,
            streamingKeptUp = new
            {
                comparedSeconds = Math.Round(compared / 2.0 / SampleRate, 1),
                identicalToWaitedRender = streamed.AsSpan(0, compared).SequenceEqual(waited.AsSpan(0, compared)),
                maxAbsoluteDifference = Math.Round(MaxDifference(streamed, waited, compared), 6)
            },
            deterministic = first == second,
            renders
        };
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output))!);
        File.WriteAllText(output, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine(JsonSerializer.Serialize(new { report.streamingKeptUp, report.deterministic }));
        return 0;
    }

    private static float[] RenderSfizz(Sfizz sfizz, PlaybackSession session, double seconds)
    {
        CaptureSink capture = new(BlockFrames);
        SfizzPlayer player = new(sfizz, capture, session, SampleRate, 0.5f);
        while (player.SubmittedSongSeconds < seconds)
        {
            player.RenderBlock();
        }
        return capture.ToArray();
    }

    /// <summary>
    /// Two renders of one song, each at its listening scale, in 20 ms frames: how closely their
    /// loudness envelopes follow each other, how many onsets one has that the other lacks, and how
    /// their level differs per octave band (a brighter or darker piano).
    /// </summary>
    private static object Compare(float[] a, float aScale, float[] b, float bScale)
    {
        const int frame = SampleRate / 50;
        int frames = Math.Min(a.Length, b.Length) / 2 / frame;
        double[] envelopeA = Envelope(a, aScale, frame, frames), envelopeB = Envelope(b, bScale, frame, frames);
        bool[] onsetA = Onsets(envelopeA), onsetB = Onsets(envelopeB);
        int matched = 0, onlyA = 0, onlyB = 0;
        for (int index = 0; index < frames; index++)
        {
            bool nearA = onsetA[index], nearB = onsetB[Math.Max(0, index - 1)] || onsetB[index] || onsetB[Math.Min(frames - 1, index + 1)];
            if (nearA && nearB)
            {
                matched++;
            }
            else if (nearA)
            {
                onlyA++;
            }
            if (onsetB[index] && !(onsetA[Math.Max(0, index - 1)] || onsetA[index] || onsetA[Math.Min(frames - 1, index + 1)]))
            {
                onlyB++;
            }
        }
        return new
        {
            envelopeCorrelation = Math.Round(Correlation(envelopeA, envelopeB), 3),
            onsetsMatched = matched,
            onsetsOnlyManaged = onlyA,
            onsetsOnlySfizz = onlyB,
            sfizzMinusManagedDbByOctave = OctaveLevels(b, bScale).Zip(OctaveLevels(a, aScale),
                (sfizz, managed) => Math.Round(sfizz - managed, 1)).ToArray()
        };
    }

    private static double[] Envelope(float[] samples, float scale, int frame, int frames)
    {
        double[] envelope = new double[frames];
        for (int index = 0; index < frames; index++)
        {
            double sum = 0;
            for (int sample = index * frame * 2; sample < (index + 1) * frame * 2; sample++)
            {
                sum += samples[sample] * (double)samples[sample];
            }
            envelope[index] = 10 * Math.Log10(Math.Max(sum * scale * scale / (frame * 2), 1e-10));
        }
        return envelope;
    }

    /// <summary>A frame at least 6 dB louder than the one before, above −50 dBFS.</summary>
    private static bool[] Onsets(double[] envelope) =>
        envelope.Select((level, index) => index > 0 && level > -50 && level - envelope[index - 1] >= 6).ToArray();

    private static double Correlation(double[] a, double[] b)
    {
        double meanA = a.Average(), meanB = b.Average(), covariance = 0, varianceA = 0, varianceB = 0;
        for (int index = 0; index < a.Length; index++)
        {
            covariance += (a[index] - meanA) * (b[index] - meanB);
            varianceA += (a[index] - meanA) * (a[index] - meanA);
            varianceB += (b[index] - meanB) * (b[index] - meanB);
        }
        return covariance / Math.Sqrt(varianceA * varianceB);
    }

    /// <summary>Level in dB of the mono mix in octave bands centred 63 Hz to 8 kHz.</summary>
    private static double[] OctaveLevels(float[] samples, float scale)
    {
        double[] centres = [63, 125, 250, 500, 1000, 2000, 4000, 8000];
        return centres.Select(centre =>
        {
            // A second-order band-pass (RBJ, constant peak gain) one octave wide.
            double w = 2 * Math.PI * centre / SampleRate, alpha = Math.Sin(w) * Math.Sinh(Math.Log(2) / 2 * w / Math.Sin(w));
            double a0 = 1 + alpha, b0 = alpha / a0, b2 = -alpha / a0, a1 = -2 * Math.Cos(w) / a0, a2 = (1 - alpha) / a0;
            double x1 = 0, x2 = 0, y1 = 0, y2 = 0, sum = 0;
            for (int index = 0; index + 1 < samples.Length; index += 2)
            {
                double x = (samples[index] + samples[index + 1]) * 0.5 * scale;
                double y = b0 * x + b2 * x2 - a1 * y1 - a2 * y2;
                x2 = x1;
                x1 = x;
                y2 = y1;
                y1 = y;
                sum += y * y;
            }
            return 10 * Math.Log10(Math.Max(sum / (samples.Length / 2), 1e-20));
        }).ToArray();
    }

    private static double MaxDifference(float[] a, float[] b, int count)
    {
        double max = 0;
        for (int index = 0; index < count; index++)
        {
            max = Math.Max(max, Math.Abs(a[index] - b[index]));
        }
        return max;
    }

    [System.Runtime.InteropServices.DllImport("winmm.dll")]
    private static extern uint timeBeginPeriod(uint milliseconds);

    private sealed class SfizzBlocks(Sfizz sfizz, SfizzPlayer player) : IBlocks
    {
        public void Render() => player.RenderBlock();
        public int Voices => sfizz.ActiveVoices;
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
    /// app's two-buffer stream could not have had ready: a dropout. A <paramref name="paced"/> run waits
    /// for each block's real-time slot before rendering the next, as a sound card would.
    /// </summary>
    private static object TimeBlocks(string piano, double rate, PlaybackSession session, Func<IAudioSink, IBlocks> create,
        double voicesFrom = 0, bool paced = false)
    {
        NullSink sink = new(BlockFrames);
        IBlocks blocks = create(sink);
        double budget = (double)BlockFrames / SampleRate;
        int count = (int)Math.Ceiling(Math.Min(RunSeconds, (session.TotalDuration + TailSeconds) / rate) / budget);
        List<double> times = new(count);
        int late = 0, peakVoices = 0;
        long started = Stopwatch.GetTimestamp();
        double busy = 0;
        for (int block = 0; block < count; block++)
        {
            long before = Stopwatch.GetTimestamp();
            blocks.Render();
            double seconds = Stopwatch.GetElapsedTime(before).TotalSeconds;
            busy += seconds;
            if (paced)
            {
                long slot = started + (long)((block + 1) * budget * Stopwatch.Frequency);
                while (Stopwatch.GetTimestamp() < slot)
                {
                    if (slot - Stopwatch.GetTimestamp() > Stopwatch.Frequency / 500)
                    {
                        Thread.Sleep(1);
                    }
                    else
                    {
                        Thread.SpinWait(64);
                    }
                }
            }
            peakVoices = Math.Max(peakVoices, blocks.Voices);
            if (block * budget >= voicesFrom)
            {
                times.Add(seconds);
                late += seconds > budget ? 1 : 0;
            }
        }
        double total = paced ? busy : Stopwatch.GetElapsedTime(started).TotalSeconds;
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
            stolenVoices = (blocks as SfzBlocks)?.Synth.StolenVoices,
            paced
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

    /// <summary>Keeps only the first <paramref name="limit"/> samples, so a ten-minute run stays small.</summary>
    private sealed class CaptureFirstSink(int blockFrames, int limit) : IAudioSink
    {
        private readonly float[] samples = new float[limit];
        private int count;
        public int BlockFrames => blockFrames;
        public bool WantsBlock => true;

        public void Submit(ReadOnlySpan<float> interleaved)
        {
            int take = Math.Min(interleaved.Length, limit - count);
            interleaved[..take].CopyTo(samples.AsSpan(count));
            count += take;
        }

        public float[] ToArray() => samples[..count];
    }

    private sealed class TeeSink(IAudioSink first, IAudioSink second) : IAudioSink
    {
        public int BlockFrames => first.BlockFrames;
        public bool WantsBlock => true;

        public void Submit(ReadOnlySpan<float> interleaved)
        {
            first.Submit(interleaved);
            second.Submit(interleaved);
        }
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
