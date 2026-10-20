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
		PianoDescription salamander = new("Salamander Grand Piano V3", "Salamander", "SalamanderGrandPianoV3.sfz",
			"Salamander Grand Piano V3 by Alexander Holm, CC BY 3.0");
		activeAudioBackend = AudioBackend.SfzPiano;
		activeAudioStatus = new AudioOutputStatus(
			AudioBackend.SfzPiano, null, 1_307_297_224, null, null, salamander);
		installedPiano = new PianoStatus(@"C:\pianos\salamander", salamander, 1_307_297_224, null);
		installedSoundFont = new SoundFontStatus(@"C:\soundfonts\YDP-GrandPiano.sf2", 118_398_836, null);

		int failures = 0;
		try
		{
			UiLayout layout = UiLayout.Create(InitialWidth, InitialHeight);

			failures += Capture(outputDirectory, "01-landing-empty", layout, () =>
			{
				OmrEngine engine = OmrEngine.Homr465;
				OmrEngine? filter = null;
				int a = 0, b = 0, c = 0;
				DrawLanding(layout, ref engine, [], [], [], ref a, ref b, ref filter, ref c, new LibrarySearchState(),
					null, out _, out _);
			});

			// The SFZ piano asked for but not installed: YDP plays, and the bar says why.
			failures += Capture(outputDirectory, "01-landing-piano-not-installed", layout, () =>
			{
				AudioBackend backend = activeAudioBackend;
				AudioOutputStatus? status = activeAudioStatus;
				PianoStatus? piano = installedPiano;
				const string problem = "Salamander is not installed. Run scripts\\install-piano.ps1, then pick it again.";
				activeAudioBackend = AudioBackend.SoundFont;
				activeAudioStatus = new AudioOutputStatus(AudioBackend.SoundFont, "YDP-GrandPiano.sf2", 118_398_836, null, problem);
				installedPiano = new PianoStatus(null, null, 0, problem);
				try
				{
					OmrEngine engine = OmrEngine.Homr480;
					OmrEngine? filter = null;
					int a = 0, b = 0, c = 0;
					DrawLanding(layout, ref engine, [], [], [], ref a, ref b, ref filter, ref c, new LibrarySearchState(),
						problem, out _, out _);
				}
				finally
				{
					activeAudioBackend = backend;
					activeAudioStatus = status;
					installedPiano = piano;
				}
			});

			// Neither piano installed: playback is silent and the bar says how to install one.
			failures += Capture(outputDirectory, "01-landing-no-piano", layout, () =>
			{
				AudioBackend backend = activeAudioBackend;
				AudioOutputStatus? status = activeAudioStatus;
				PianoStatus? piano = installedPiano;
				SoundFontStatus? font = installedSoundFont;
				activeAudioBackend = AudioBackend.Silent;
				activeAudioStatus = new AudioOutputStatus(AudioBackend.Silent, null, 0, null, AudioOutput.NoPianoProblem);
				installedPiano = new PianoStatus(null, null, 0, "Salamander is not installed.");
				installedSoundFont = null;
				try
				{
					OmrEngine engine = OmrEngine.Homr480;
					OmrEngine? filter = null;
					int a = 0, b = 0, c = 0;
					DrawLanding(layout, ref engine, [], [], [], ref a, ref b, ref filter, ref c, new LibrarySearchState(),
						AudioOutput.NoPianoProblem, out _, out _);
				}
				finally
				{
					activeAudioBackend = backend;
					activeAudioStatus = status;
					installedPiano = piano;
					installedSoundFont = font;
				}
			});

			failures += Capture(outputDirectory, "02-landing-populated", layout, () =>
			{
				OmrEngine engine = OmrEngine.Homr480;
				OmrEngine? filter = null;
				int a = 0, b = 0, c = 0;
				DrawLanding(layout, ref engine, SamplePdfs(), SampleCached(), SampleMidis(),
					ref a, ref b, ref filter, ref c, new LibrarySearchState(), null, out _, out _);
			});

			// Same page filtered to one engine, to prove the tab selection renders.
			failures += Capture(outputDirectory, "03-landing-filtered-zeus", layout, () =>
			{
				// Zeus is no longer offered, but the songs it converted still play from the playlist.
				OmrEngine engine = OmrEngine.Homr465;
				OmrEngine? filter = OmrEngine.Zeus;
				int a = 0, b = 0, c = 0;
				DrawLanding(layout, ref engine, SamplePdfs(), SampleCached(), SampleMidis(),
					ref a, ref b, ref filter, ref c, new LibrarySearchState(), "Conversion cancelled. No partial cache was saved.", out _, out _);
			});

			failures += Capture(outputDirectory, "04-confirm-reuse", layout, () =>
				DrawConfirmReuse(layout, new LoadRequest(
					@"C:\scores\Sample Score.pdf", OmrEngine.Homr480, false, null)));

			failures += Capture(outputDirectory, "05-processing", layout, () =>
			{
				LoadProgressModel model = new();
				model.Start("Sample Score.pdf", OmrEngine.Homr480);
				model.Apply(new OmrProgress
				{
					Engine = OmrEngine.Homr480,
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
					new LoadRequest(@"C:\scores\Sample Score.pdf", OmrEngine.Homr480, false, null)));

			failures += Capture(outputDirectory, "06-error-465-fallback", layout, () =>
				DrawError(layout, new OmrPipelineException("Pinned model assets are unavailable.",
					errorCode: "MODEL_INVALID", stage: "admission", exitCode: 8),
					new LoadRequest(@"C:\scores\Sample Score.pdf", OmrEngine.Homr465, false, null)));

			// A conversion cached as MIDI before songs kept their score: the legacy badge, and the screen
			// as it opens, with EXPRESSION and EXPORT closed.
			failures += Capture(outputDirectory, "07-playback", layout, () =>
			{
				songOverlay = SongOverlay.Empty;
				List<Note> notes = SampleNotes();
				// Frozen clock. A live one starts counting the moment the controller is
				// built, so a millisecond or two passes before the notes are drawn and they
				// land a pixel lower - enough to change the PNG between runs and make this
				// screen useless as a reference image for refactoring.
				PlaybackController playback = new(
					new PlaybackSession(notes),
					new NullMidiOutput(),
					new PlaybackClock(() => 0));
				SongLoadResult song = new(notes, "Sample Score", OmrEngine.Homr, true, null);
				Keyboard piano = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);
				GameState state = GameState.Playing;
				DrawPlayback(playback, song, piano, false, 0.0, new PlaybackRateEditor(), new AudioOffsetEditor(),
					ref state, layout);
			});

			// A song played from its score with the EXPRESSION panel open, so its switches show lit;
			// the screen above shows the panel closed.
			failures += Capture(outputDirectory, "07-playback-expression", layout, () =>
			{
				List<Note> notes = SampleNotes();
				PlaybackController playback = new(
					new PlaybackSession(notes),
					new NullMidiOutput(),
					new PlaybackClock(() => 0));
				SongLoadResult song = new(notes, "Sample Score", OmrEngine.MusicXml, true, null, SmokePerformance());
				Keyboard piano = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);
				GameState state = GameState.Playing;
				RebuildOverlay(song, expression, ExpressionPlayback.ForSong(song, expression).Pedal);
				expressionPanelOpen = true;
				DrawPlayback(playback, song, piano, false, 0.0, new PlaybackRateEditor(), new AudioOffsetEditor(),
					ref state, layout);
				expressionPanelOpen = false;
				songOverlay = SongOverlay.Empty;
			});

			// A HOMR 480 song part-way through a repeat: hands coloured by staff, bar lines and the
			// pedal lane with one span held and one to come, the TIMING FIX badge and the score's counts,
			// and the EXPORT panel open with its status line after a MIDI export.
			failures += Capture(outputDirectory, "07-playback-score", layout, () =>
			{
				SongPerformance performance = SmokeScore();
				SongPlayback timeline = ExpressionPlayback.ForSong(
					new SongLoadResult([], "Sample Score", OmrEngine.Homr480, true, null, performance), expression);
				SongLoadResult song = new(timeline.Notes, "Sample Score", OmrEngine.Homr480, true, null, performance);
				PlaybackController playback = new(
					new PlaybackSession(timeline.Notes, pedal: timeline.Pedal),
					new NullMidiOutput(),
					new PlaybackClock(() => 0));
				playback.Seek(9.0, resume: false);
				RebuildOverlay(song, expression, timeline.Pedal);
				Keyboard piano = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);
				GameState state = GameState.Playing;
				string? status = exportStatus;
				exportStatus = @"Saved to C:\Users\you\AppData\Local\Sheet2Play\exports\Sample Score.mid";
				exportPanelOpen = true;
				try
				{
					DrawPlayback(playback, song, piano, false, 0.0, new PlaybackRateEditor(), new AudioOffsetEditor(),
						ref state, layout);
				}
				finally
				{
					exportPanelOpen = false;
					exportStatus = status;
					songOverlay = SongOverlay.Empty;
				}
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
		new(@"C:\scores\Sample Score.pdf", "Sample Score", 1_482_112, DateTimeOffset.UtcNow),
		new(@"C:\scores\Dexter Main Theme.pdf", "Dexter Main Theme", 733_184, DateTimeOffset.UtcNow),
		new(@"C:\scores\Homelander's Theme.png", "Homelander's Theme", 2_201_088, DateTimeOffset.UtcNow)
	];

	private static MidiLibraryEntry[] SampleMidis() =>
	[
		new(@"C:\midi\Evening Prelude.mid", "Evening Prelude", 26_955, DateTimeOffset.UtcNow),
		new(@"C:\midi\Study in C.mid", "Study in C", 8_911, DateTimeOffset.UtcNow),
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

	/// <summary>Two measures played twice, with a pedal mark, a dynamic and a staccato.</summary>
	private static SongPerformance SmokePerformance() => new(
		SongPerformance.CurrentSchemaVersion, "musicxml", [], false, [], [],
		[
			new SongMeasure(0, 0, "1", 0, 4, 4, [4, 4], false, true, 0, null, false, null),
			new SongMeasure(1, 0, "2", 4, 4, 4, [4, 4], false, false, 1, null, false, null)
		],
		[0, 1, 0, 1],
		[new SongNote("C4", 60, 0, 0, 1, 0, 0, "1", false, false, false, ["staccato"], [])],
		[new SongPedal(0, 0, 0, 1, "start", "mark")],
		[new SongDynamic(0, 0, 0, 0, "p", null)],
		[], [], default, []);

	/// <summary>
	/// Four bars of a two-staff piano part, bars 3 and 4 repeated, with the pedal held through bar 2
	/// and pressed again in bar 4, and feature counts for the header.
	/// </summary>
	private static SongPerformance SmokeScore()
	{
		List<SongNote> notes = [];
		for (int measure = 0; measure < 4; measure++)
		{
			for (int beat = 0; beat < 4; beat++)
			{
				notes.Add(new SongNote("E5", 76 + (measure + beat) % 5, measure, beat, 1, 0, 0, "1", false, false, false,
					beat == 0 ? ["accent"] : [], []));
			}
			notes.Add(new SongNote("C3", 48 + measure, measure, 0, 4, 0, 1, "2", false, false, false, [], []));
		}
		using System.Text.Json.JsonDocument features = System.Text.Json.JsonDocument.Parse(
			"""{"articulation_marks": 4, "pedal_marks": 3, "dynamics_marks": 0, "repeat_backward": 1}""");
		return new SongPerformance(
			SongPerformance.CurrentSchemaVersion, "omr-pages", [], true, [new SongPart(0, 2, "Piano")], [],
			[
				new SongMeasure(0, 0, "1", 0, 4, 4, [4, 4], false, false, 0, null, false, null),
				new SongMeasure(1, 0, "2", 4, 4, 4, [4, 4], false, false, 0, null, false, null),
				new SongMeasure(2, 0, "3", 8, 4, 4, [4, 4], false, true, 0, null, false, null),
				new SongMeasure(3, 0, "4", 12, 4, 4, [4, 4], false, false, 1, null, false, null)
			],
			[0, 1, 2, 3, 2, 3],
			notes,
			[
				new SongPedal(1, 0, 0, 1, "start", "mark"),
				new SongPedal(1, 3.5, 0, 1, "stop", "mark"),
				new SongPedal(3, 1, 0, 1, "start", "mark")
			],
			[], [], [], features.RootElement.Clone(), []);
	}
}
