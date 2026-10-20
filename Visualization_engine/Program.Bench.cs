using Raylib_cs;

namespace SynthesiaClone;

/// <summary>
/// Measures how long the playback screen takes to draw, via `--bench`.
///
/// It exists because a report of dropped frames could not be checked against anything: the app had no
/// frame-time readout, and clicking through the UI produces numbers nobody can reproduce. This runs
/// the real <c>DrawPlayback</c> against a real song at a real position, with a null MIDI output and
/// no audio device, so what it measures is the draw path alone.
///
/// That isolation is the point. If a dense score cannot be drawn inside a frame budget here, where
/// no audio is being synthesised at all, then the frame drops are not caused by the audio engine -
/// which is the question this was written to settle.
///
/// <c>--audio sfz|ydp</c> asks the opposite question: whether the piano keeps up while the screen is
/// drawn. It opens the real audio output, muted, plays the song on the audio thread at real time
/// (<c>--rate</c> for faster), draws every frame at 144 fps as the app does, and reports the
/// stream's underruns, the piano's load time and the commit charge it added. <c>--audio clock</c> is
/// its control: the same real-time playback on the stopwatch clock, with no audio at all.
/// </summary>
internal static partial class Program
{
	private const int BenchDefaultFrames = 600;

	private static int RunBench(string[] args)
	{
		if (args.Length < 2 || args[1].StartsWith("--", StringComparison.Ordinal))
		{
			Console.Error.WriteLine(
				"[BENCH] Usage: --bench <song> [--frames 600] [--start 30] [--width 1280] [--height 720] " +
				"[--audio sfz|ydp|clock] [--rate 1.0]");
			return 1;
		}

		string source = args[1];
		if (!File.Exists(source))
		{
			Console.Error.WriteLine("[BENCH] Source not found: " + source);
			return 1;
		}

		int frames = (int)ParseDemoDouble(GetDemoOption(args, "--frames"), BenchDefaultFrames);
		double start = ParseDemoDouble(GetDemoOption(args, "--start"), 30.0);
		int width = (int)ParseDemoDouble(GetDemoOption(args, "--width"), InitialWidth);
		int height = (int)ParseDemoDouble(GetDemoOption(args, "--height"), InitialHeight);

		SongLoadResult song;
		try
		{
			// Not recorded as recently opened: a measurement is not the user opening a song.
			song = SongCache.LoadOrCreateDetailed(source, AppSettingsStore.LoadEngine(), recordRecent: false);
		}
		catch (Exception error)
		{
			Console.Error.WriteLine("[BENCH] Could not load the song: " + error.Message);
			return 1;
		}

		string? audioOption = GetDemoOption(args, "--audio");
		if (audioOption is not (null or "sfz" or "ydp" or "clock"))
		{
			Console.Error.WriteLine("[BENCH] --audio is sfz, ydp or clock.");
			return 1;
		}
		double rate = ParseDemoDouble(GetDemoOption(args, "--rate"), 1.0);
		// With audio, the song plays as the app plays it: expression, pedal and all.
		PlaybackSession session;
		if (audioOption is null)
		{
			session = new(song.Notes);
		}
		else
		{
			SongPlayback expressive = ExpressionPlayback.ForSong(song, AppSettingsStore.LoadExpression());
			session = new(expressive.Notes, pedal: expressive.Pedal);
		}
		start = Math.Clamp(start, 0, Math.Max(0, session.TotalDuration - 1));

		// --vsync reproduces the real app's presentation: VSyncHint plus SetTargetFPS(144), on a
		// visible window. Without it the bench measures raw draw cost; with it, it measures frame
		// PACING, which is a different question - a frame can be drawn in 1ms and still be presented
		// late if the two throttles disagree.
		bool withVsync = args.Any(a => string.Equals(a, "--vsync", StringComparison.OrdinalIgnoreCase));
		bool withTargetFps = args.Any(a => string.Equals(a, "--target-fps", StringComparison.OrdinalIgnoreCase));
		// Audio plays in real time, so the frames must be paced like the app's.
		withTargetFps |= audioOption is not null;
		if (withVsync)
		{
			Raylib.SetConfigFlags(ConfigFlags.VSyncHint);
		}
		else if (!withTargetFps)
		{
			Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
		}
		Raylib.InitWindow(width, height, "Sheet2Play (bench)");
		if (withTargetFps)
		{
			Raylib.SetTargetFPS(144);
		}
		UiTheme.InitializeFonts();

		try
		{
			UiLayout layout = UiLayout.Create(width, height);
			Keyboard piano = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);

			// The clock is a plain variable so each frame is drawn for an exact position, which makes
			// the run reproducible and lets the position advance at a fixed rate regardless of how
			// long a frame actually took.
			double position = start;
			AudioOutput? audio = null;
			PlaybackController playback;
			bool live = audioOption is not null;
			if (audioOption == "clock")
			{
				playback = new(session, new NullMidiOutput(), new PlaybackClock());
				playback.SetPlaybackRate(rate);
				playback.Seek(start, resume: true);
				activeAudioBackend = AudioBackend.MidiDevice;
				activeAudioStatus = new AudioOutputStatus(AudioBackend.MidiDevice, null, 0, "bench", null);
			}
			else if (audioOption is null)
			{
				playback = new(
					session,
					new NullMidiOutput(),
					new PlaybackClock(() => position));
				playback.Seek(start, resume: false);
				activeAudioBackend = AudioBackend.MidiDevice;
				activeAudioStatus = new AudioOutputStatus(AudioBackend.MidiDevice, null, 0, "bench", null);
			}
			else
			{
				AudioBackend backend = audioOption == "sfz" ? AudioBackend.SfzPiano : AudioBackend.SoundFont;
				using System.Diagnostics.Process self = System.Diagnostics.Process.GetCurrentProcess();
				self.Refresh();
				long privateBefore = self.PrivateMemorySize64;
				System.Diagnostics.Stopwatch loading = System.Diagnostics.Stopwatch.StartNew();
				audio = AudioOutput.Create(backend, AppSettingsStore.LoadSoundFontPath());
				double loadSeconds = loading.Elapsed.TotalSeconds;
				self.Refresh();
				if (audio.Backend != backend)
				{
					Console.Error.WriteLine($"[BENCH] Could not open {backend}: {audio.Status.Problem}");
					audio.Dispose();
					return 1;
				}
				audio.Mute();
				Console.WriteLine($"[BENCH] piano     {backend}, loaded in {loadSeconds:0.00} s, " +
					$"commit +{(self.PrivateMemorySize64 - privateBefore) / 1024.0 / 1024.0:0.0} MB");
				double offset = AppSettingsStore.ResolveAudioOffsetMilliseconds(backend, audio.BufferedSeconds) / 1000.0;
				playback = new(session, audio.MidiOutput, audio.CreateTimebase(session, offset));
				playback.SetPlaybackRate(rate);
				playback.Seek(start, resume: true);
				activeAudioBackend = audio.Backend;
				activeAudioStatus = audio.Status;
			}

			FrameTimeTracker tracker = new();
			int visiblePeak = 0;
			// Where each underrun happened, so one at the start (filling an empty stream) can be told
			// from one mid-song.
			List<double> underrunsAt = [];
			double step = 1.0 / 144.0;

			for (int frame = 0; frame < frames; frame++)
			{
				position = start + (frame * step);
				if (live)
				{
					audio?.Pump();
					playback.Update();
					if (audio is not null && audio.UnderrunCount > underrunsAt.Count)
					{
						underrunsAt.Add(playback.Position);
					}
				}
				double frameStarted = System.Diagnostics.Stopwatch.GetTimestamp()
					/ (double)System.Diagnostics.Stopwatch.Frequency;

				GameState state = GameState.Playing;
				Raylib.BeginDrawing();
				Raylib.ClearBackground(UiTheme.Background);
				DrawPlayback(playback, song, piano, false, 0.0, new PlaybackRateEditor(),
					new AudioOffsetEditor(), ref state, layout);

				// Recorded BEFORE EndDrawing, matching the main loop. Under vsync, EndDrawing blocks
				// until the next refresh, so including it would measure the wait rather than the
				// work and report every frame as "late" by construction.
				tracker.Record((System.Diagnostics.Stopwatch.GetTimestamp()
					/ (double)System.Diagnostics.Stopwatch.Frequency - frameStarted) * 1000.0);
				Raylib.EndDrawing();

				double lookAhead = Math.Max(1.0, (double)(layout.HitLineY - layout.HeaderHeight) / layout.FallSpeed + 1.0);
				(int Start, int End) range = session.GetVisibleRange(live ? playback.Position : position, 1.0, lookAhead);
				visiblePeak = Math.Max(visiblePeak, range.End - range.Start);
			}

			Console.WriteLine($"[BENCH] song      {Path.GetFileName(source)} " +
				$"({session.Notes.Count:N0} notes, {PlaybackFormatting.FormatTime(session.TotalDuration)})");
			Console.WriteLine($"[BENCH] window    {width}x{height}   from {start:0.0}s, {frames} frames");
			Console.WriteLine($"[BENCH] visible   {visiblePeak} notes at peak");
			Console.WriteLine(tracker.Summarise(Path.GetFileNameWithoutExtension(source)));
			if (audio is not null)
			{
				Console.WriteLine($"[BENCH] audio     {playback.Position - start:0.0} song seconds at {rate:0.00}x, " +
					$"{audio.UnderrunCount} underruns" +
					(underrunsAt.Count == 0 ? string.Empty : $" (at {string.Join(", ", underrunsAt.Select(at => $"{at:0.00} s"))})"));
				audio.Dispose();
			}
			return 0;
		}
		catch (Exception error)
		{
			Console.Error.WriteLine("[BENCH] Failed: " + error);
			return 1;
		}
		finally
		{
			UiTheme.ShutdownFonts();
			Raylib.CloseWindow();
		}
	}
}
