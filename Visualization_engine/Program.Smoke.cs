using Raylib_cs;
using Rectangle = Raylib_cs.Rectangle;
using Color = Raylib_cs.Color;
using Image = Raylib_cs.Image;

namespace SynthesiaClone;

/// <summary>
/// Headless rendering pass used by `--smoke`. It opens a hidden window, draws every UI
/// state to an offscreen target with synthetic data, and writes one PNG per state.
///
/// The point is that frontend changes can be checked without a human launching the app:
/// a non-zero exit means a screen threw, and the PNGs show what actually rendered.
/// It is a partial of <see cref="Program"/> so it can reach the private Draw* methods
/// and the private LoadRequest record without widening their visibility.
/// </summary>
internal static partial class Program
{
	private static int RunSmoke(string outputDirectory)
	{
		Directory.CreateDirectory(outputDirectory);
		Raylib.SetConfigFlags(ConfigFlags.ResizableWindow | ConfigFlags.HiddenWindow);
		Raylib.InitWindow(InitialWidth, InitialHeight, "Sheet2Play (smoke)");
		Raylib.SetTargetFPS(60);
		UiTheme.InitializeFonts();

		// Report the real library too. The screens below use synthetic data, so without
		// this a packaged build could render perfectly while pointing at an empty folder.
		try
		{
			Console.WriteLine($"[SMOKE] library   {SongCache.ApplicationDirectory}");
			Console.WriteLine($"[SMOKE] contents  {SongCache.GetPdfLibrary().Count} pdf, " +
				$"{SongCache.GetMidiLibrary().Count} midi, " +
				$"{SongCache.GetCachedSongs().Count} cached");
		}
		catch (Exception exception)
		{
			Console.Error.WriteLine("[SMOKE] library scan failed: " + exception.Message);
		}

		// Fabricated rather than queried, so these PNGs are identical on any machine - including
		// one with no audio device and no soundfont installed. The audio system is never opened
		// here; InitAudioDevice belongs to RunApplication alone.
		activeAudioBackend = AudioBackend.SoundFont;
		selectedAudioBackend = AudioBackend.SoundFont;
		activeAudioStatus = new AudioOutputStatus(
			AudioBackend.SoundFont, "YDP-GrandPiano.sf2", 118_398_836, null, null);

		int failures = 0;
		try
		{
			UiLayout layout = UiLayout.Create(InitialWidth, InitialHeight);

			failures += Capture(outputDirectory, "01-landing-empty", layout, () =>
			{
				OmrEngine engine = OmrEngine.Homr;
				OmrEngine? filter = null;
				int a = 0, b = 0, c = 0;
				DrawLanding(layout, ref engine, [], [], [], ref a, ref b, ref filter, ref c, new LibrarySearchState(),
					null, out _, out _);
			});

			failures += Capture(outputDirectory, "02-landing-populated", layout, () =>
			{
				OmrEngine engine = OmrEngine.Homr;
				OmrEngine? filter = null;
				int a = 0, b = 0, c = 0;
				DrawLanding(layout, ref engine, SamplePdfs(), SampleCached(), SampleMidis(),
					ref a, ref b, ref filter, ref c, new LibrarySearchState(), null, out _, out _);
			});

			// Same page filtered to one engine, to prove the tab selection renders.
			failures += Capture(outputDirectory, "03-landing-filtered-zeus", layout, () =>
			{
				OmrEngine engine = OmrEngine.Zeus;
				OmrEngine? filter = OmrEngine.Zeus;
				int a = 0, b = 0, c = 0;
				DrawLanding(layout, ref engine, SamplePdfs(), SampleCached(), SampleMidis(),
					ref a, ref b, ref filter, ref c, new LibrarySearchState(), "Zeus finished with warnings.", out _, out _);
			});

			failures += Capture(outputDirectory, "04-confirm-reuse", layout, () =>
				DrawConfirmReuse(layout, new LoadRequest(
					@"C:\scores\Liyue Battle Theme.pdf", OmrEngine.Homr, false, null)));

			failures += Capture(outputDirectory, "05-processing", layout, () =>
			{
				LoadProgressModel model = new();
				model.Start("Liyue Battle Theme.pdf", OmrEngine.Homr);
				model.Apply(new OmrProgress
				{
					Engine = OmrEngine.Homr,
					Stage = OmrProgressStages.MusicXmlExport,
					Status = OmrProgressStatuses.Started,
					Message = "Exporting MusicXML",
					Page = 3,
					PageCount = 8,
					CompletedPages = 2
				});
				DrawProcessing(layout, model, cancelling: false);
			});

			failures += Capture(outputDirectory, "06-error", layout, () =>
				DrawError(layout, new OmrPipelineException(
					"note duration must be positive; received 0.0",
					errorCode: "NORMALIZATION_FAILED",
					stage: "normalize",
					exitCode: 7,
					page: 8),
					new LoadRequest(@"C:\scores\Liyue Battle Theme.pdf", OmrEngine.Homr, false, null)));

			failures += Capture(outputDirectory, "07-playback", layout, () =>
			{
				List<Note> notes = SampleNotes();
				// Frozen clock. A live one starts counting the moment the controller is
				// built, so a millisecond or two passes before the notes are drawn and they
				// land a pixel lower - enough to change the PNG between runs and make this
				// screen useless as a reference image for refactoring.
				PlaybackController playback = new(
					new PlaybackSession(notes),
					new NullMidiOutput(),
					new PlaybackClock(() => 0));
				SongLoadResult song = new(notes, "Liyue Battle Theme", OmrEngine.Homr, true, null);
				Keyboard piano = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);
				GameState state = GameState.Playing;
				DrawPlayback(playback, song, piano, false, 0.0, new PlaybackRateEditor(), new AudioOffsetEditor(),
					ref state, layout);
			});
		}
		catch (Exception exception)
		{
			Console.Error.WriteLine("[SMOKE] Unhandled failure: " + exception);
			failures++;
		}
		finally
		{
			UiTheme.ShutdownFonts();
			Raylib.CloseWindow();
		}

		Console.WriteLine(failures == 0
			? $"[SMOKE] All screens rendered. PNGs in {outputDirectory}"
			: $"[SMOKE] {failures} screen(s) failed.");
		return (failures == 0) ? 0 : 1;
	}

	/// <summary>
	/// Renders one screen to an offscreen target and writes it as a PNG. Returns 1 if the
	/// screen threw, so one broken panel does not hide the others.
	/// </summary>
	private static int Capture(string outputDirectory, string name, UiLayout layout, Action draw)
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
			// Render textures are stored bottom-up; flip so the PNG reads the right way round.
			Raylib.ImageFlipVertical(ref image);
			Raylib.ExportImage(image, Path.Combine(outputDirectory, name + ".png"));
			Raylib.UnloadImage(image);
			Console.WriteLine("[SMOKE] ok   " + name);
			return 0;
		}
		catch (Exception exception)
		{
			Console.Error.WriteLine($"[SMOKE] FAIL {name}: {exception.GetType().Name}: {exception.Message}");
			return 1;
		}
		finally
		{
			Raylib.UnloadRenderTexture(target);
		}
	}

	private static PdfLibraryEntry[] SamplePdfs() =>
	[
		new(@"C:\scores\Liyue Battle Theme.pdf", "Liyue Battle Theme", 1_482_112, DateTimeOffset.UtcNow),
		new(@"C:\scores\Dexter Main Theme.pdf", "Dexter Main Theme", 733_184, DateTimeOffset.UtcNow),
		new(@"C:\scores\Homelander's Theme.png", "Homelander's Theme", 2_201_088, DateTimeOffset.UtcNow)
	];

	private static MidiLibraryEntry[] SampleMidis() =>
	[
		new(@"C:\midi\Beyond This Station.mid", "Beyond This Station", 26_955, DateTimeOffset.UtcNow),
		new(@"C:\midi\Coronal Radiance.mid", "Coronal Radiance", 8_911, DateTimeOffset.UtcNow),
		new(@"C:\midi\in the pool.mxl", "in the pool", 14_233, DateTimeOffset.UtcNow)
	];

	/// <summary>Two engines, so the ALL/HOMR/ZEUS filter tabs all have something to show.</summary>
	private static CachedSongEntry[] SampleCached() =>
	[
		new(new RecentSongEntry("songs/midi/homr/alpha.mid.cache.json", "Alpha Score",
			OmrEngine.Homr, DateTimeOffset.UtcNow), 1240, 182.5),
		new(new RecentSongEntry("songs/midi/homr/beta.mid.cache.json", "Beta Score",
			OmrEngine.Homr, DateTimeOffset.UtcNow), 880, 141.0),
		new(new RecentSongEntry("songs/midi/zeus/gamma.mid.cache.json", "Gamma Score",
			OmrEngine.Zeus, DateTimeOffset.UtcNow), 2310, 298.25)
	];

	private static List<Note> SampleNotes()
	{
		List<Note> notes = [];
		for (int index = 0; index < 48; index++)
		{
			notes.Add(new Note(
				24 + index % 40,
				index * 0.25,
				0.45,
				96,
				(index % 2 == 0) ? UiTheme.Sky : UiTheme.Lime));
		}
		return notes;
	}
}
