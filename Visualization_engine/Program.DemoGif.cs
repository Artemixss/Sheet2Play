using Raylib_cs;
using Image = Raylib_cs.Image;

namespace SynthesiaClone;

/// <summary>
/// Renders the playback screen to a numbered PNG sequence for the README demo, via
/// `--smoke-gif`. `scripts/make-demo-gif.py` assembles the frames into an animated GIF.
///
/// The demo is generated rather than screen-recorded so it can be refreshed whenever the
/// frontend changes, instead of going stale the moment the UI moves. Frames are driven by
/// an injected clock rather than wall time, so the output is identical on every run and
/// does not stutter when a frame takes longer to draw than its slot.
/// </summary>
internal static partial class Program
{
	private const int DemoDefaultFps = 25;
	private const double DemoDefaultSeconds = 4.0;

	private static int RunDemoGif(string[] args)
	{
		string outputDirectory = (args.Length > 1 && !args[1].StartsWith("--", StringComparison.Ordinal))
			? args[1]
			: Path.Combine(Path.GetTempPath(), "sheet2play-demo");
		string? source = GetDemoOption(args, "--source");
		double seconds = ParseDemoDouble(GetDemoOption(args, "--seconds"), DemoDefaultSeconds);
		int fps = (int)ParseDemoDouble(GetDemoOption(args, "--fps"), DemoDefaultFps);
		double? explicitStart = GetDemoOption(args, "--start") is string raw
			? ParseDemoDouble(raw, 0)
			: null;

		source ??= FindDemoSource();
		if (source is null)
		{
			Console.Error.WriteLine(
				"[DEMO] No source given and no MIDI found in the library. Pass --source <file>.");
			return 1;
		}
		if (!File.Exists(source))
		{
			Console.Error.WriteLine("[DEMO] Source not found: " + source);
			return 1;
		}

		Directory.CreateDirectory(outputDirectory);
		Raylib.SetConfigFlags(ConfigFlags.ResizableWindow | ConfigFlags.HiddenWindow);
		Raylib.InitWindow(InitialWidth, InitialHeight, "Sheet2Play (demo)");
		Raylib.SetTargetFPS(60);
		UiTheme.InitializeFonts();

		try
		{
			SongLoadResult song = SongCache.LoadOrCreateDetailed(source, OmrEngine.DirectMidi);
			PlaybackSession session = new(song.Notes);
			double start = explicitStart ?? FindDensestStart(session.Notes, seconds);
			Console.WriteLine($"[DEMO] source    {Path.GetFileName(source)} ({session.Notes.Count} notes)");
			Console.WriteLine($"[DEMO] window    {start:0.0}s to {start + seconds:0.0}s at {fps} fps");

			// The clock is a plain variable, so a frame is rendered for an exact position
			// rather than for however long the previous frame happened to take.
			double now = 0;
			PlaybackController playback = new(session, new NullMidiOutput(), new PlaybackClock(() => now));
			playback.Seek(start, resume: true);

			UiLayout layout = UiLayout.Create(InitialWidth, InitialHeight);
			Keyboard piano = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);
			PlaybackRateEditor rateEditor = new();
			int frameCount = Math.Max(1, (int)Math.Round(seconds * fps));

			for (int frame = 0; frame < frameCount; frame++)
			{
				now = (double)frame / fps;
				playback.Update();
				GameState state = GameState.Playing;
				int failed = CaptureQuiet(
					outputDirectory,
					$"frame-{frame:D4}",
					layout,
					() => DrawPlayback(playback, song, piano, false, 0.0, rateEditor, ref state, layout));
				if (failed != 0)
				{
					return 1;
				}
			}

			Console.WriteLine($"[DEMO] wrote     {frameCount} frames to {outputDirectory}");
			return 0;
		}
		catch (Exception exception)
		{
			Console.Error.WriteLine("[DEMO] Failed: " + exception);
			return 1;
		}
		finally
		{
			UiTheme.ShutdownFonts();
			Raylib.CloseWindow();
		}
	}

	/// <summary>
	/// Start time of the busiest <paramref name="windowSeconds"/> of the score, by note
	/// onsets. Opening on the densest passage keeps the demo from starting on the sparse
	/// first bars, which is where most piano scores are least interesting to look at.
	/// Notes are already ordered by start time, so one pass with two indices is enough.
	/// </summary>
	private static double FindDensestStart(IReadOnlyList<Note> notes, double windowSeconds)
	{
		int best = 0;
		double bestStart = 0;
		int right = 0;
		for (int left = 0; left < notes.Count; left++)
		{
			double windowStart = notes[left].StartTime;
			while (right < notes.Count && notes[right].StartTime < windowStart + windowSeconds)
			{
				right++;
			}
			if (right - left > best)
			{
				best = right - left;
				bestStart = windowStart;
			}
		}
		return bestStart;
	}

	/// <summary>Prefers a score whose name looks dense, then simply the largest file.</summary>
	private static string? FindDemoSource()
	{
		try
		{
			return SongCache.GetMidiLibrary()
				.OrderByDescending(entry =>
					entry.DisplayName.Contains("moonlight", StringComparison.OrdinalIgnoreCase) ? 1 : 0)
				.ThenByDescending(entry => entry.SizeBytes)
				.Select(entry => entry.FullPath)
				.FirstOrDefault();
		}
		catch (Exception exception)
		{
			Console.Error.WriteLine("[DEMO] Library scan failed: " + exception.Message);
			return null;
		}
	}

	private static string? GetDemoOption(string[] args, string name)
	{
		for (int index = 0; index < args.Length - 1; index++)
		{
			if (string.Equals(args[index], name, StringComparison.OrdinalIgnoreCase))
			{
				return args[index + 1];
			}
		}
		return null;
	}

	private static double ParseDemoDouble(string? value, double fallback) =>
		double.TryParse(value, System.Globalization.NumberStyles.Float,
			System.Globalization.CultureInfo.InvariantCulture, out double parsed)
			? parsed
			: fallback;

	/// <summary>
	/// Same capture as the smoke pass, without a log line per frame - a six second clip is
	/// dozens of frames and the per-frame chatter buries the actual result.
	/// </summary>
	private static int CaptureQuiet(string outputDirectory, string name, UiLayout layout, Action draw)
	{
		RenderTexture2D target = Raylib.LoadRenderTexture(layout.Width, layout.Height);
		try
		{
			Raylib.BeginTextureMode(target);
			Raylib.ClearBackground(UiTheme.Background);
			try
			{
				draw();
			}
			finally
			{
				Raylib.EndTextureMode();
			}

			Image image = Raylib.LoadImageFromTexture(target.Texture);
			Raylib.ImageFlipVertical(ref image);
			Raylib.ExportImage(image, Path.Combine(outputDirectory, name + ".png"));
			Raylib.UnloadImage(image);
			return 0;
		}
		catch (Exception exception)
		{
			Console.Error.WriteLine($"[DEMO] FAIL {name}: {exception.GetType().Name}: {exception.Message}");
			return 1;
		}
		finally
		{
			Raylib.UnloadRenderTexture(target);
		}
	}
}
