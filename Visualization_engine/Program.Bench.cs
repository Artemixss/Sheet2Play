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
/// </summary>
internal static partial class Program
{
	private const int BenchDefaultFrames = 600;

	private static int RunBench(string[] args)
	{
		if (args.Length < 2 || args[1].StartsWith("--", StringComparison.Ordinal))
		{
			Console.Error.WriteLine(
				"[BENCH] Usage: --bench <song> [--frames 600] [--start 30] [--width 1280] [--height 720]");
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
			song = SongCache.LoadOrCreateDetailed(source, AppSettingsStore.LoadEngine());
		}
		catch (Exception error)
		{
			Console.Error.WriteLine("[BENCH] Could not load the song: " + error.Message);
			return 1;
		}

		PlaybackSession session = new(song.Notes);
		start = Math.Clamp(start, 0, Math.Max(0, session.TotalDuration - 1));

		// --vsync reproduces the real app's presentation: VSyncHint plus SetTargetFPS(144), on a
		// visible window. Without it the bench measures raw draw cost; with it, it measures frame
		// PACING, which is a different question - a frame can be drawn in 1ms and still be presented
		// late if the two throttles disagree.
		bool withVsync = args.Any(a => string.Equals(a, "--vsync", StringComparison.OrdinalIgnoreCase));
		bool withTargetFps = args.Any(a => string.Equals(a, "--target-fps", StringComparison.OrdinalIgnoreCase));
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
			PlaybackController playback = new(
				session,
				new NullMidiOutput(),
				new PlaybackClock(() => position));
			playback.Seek(start, resume: false);

			activeAudioBackend = AudioBackend.MidiDevice;
			activeAudioStatus = new AudioOutputStatus(AudioBackend.MidiDevice, null, 0, "bench", null);

			FrameTimeTracker tracker = new();
			int visiblePeak = 0;
			double step = 1.0 / 144.0;

			for (int frame = 0; frame < frames; frame++)
			{
				position = start + (frame * step);
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
				(int Start, int End) range = session.GetVisibleRange(position, 1.0, lookAhead);
				visiblePeak = Math.Max(visiblePeak, range.End - range.Start);
			}

			Console.WriteLine($"[BENCH] song      {Path.GetFileName(source)} " +
				$"({session.Notes.Count:N0} notes, {PlaybackFormatting.FormatTime(session.TotalDuration)})");
			Console.WriteLine($"[BENCH] window    {width}x{height}   from {start:0.0}s, {frames} frames");
			Console.WriteLine($"[BENCH] visible   {visiblePeak} notes at peak");
			Console.WriteLine(tracker.Summarise(Path.GetFileNameWithoutExtension(source)));
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
