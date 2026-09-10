using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Melanchall.DryWetMidi.Multimedia;
using Raylib_cs;
using Rectangle = Raylib_cs.Rectangle;
using Color = Raylib_cs.Color;


namespace SynthesiaClone;

public enum GameState
{
	WaitingForFile,
	ConfirmReuse,
	Processing,
	Cancelling,
	Error,
	Playing,
	Completed
}

internal static partial class Program
{
	private sealed class Win32Window : IWin32Window
	{
		public nint Handle { get; }

		public Win32Window(nint handle)
		{
			Handle = handle;
			
		}
	}

	private sealed class DialogState
	{
		public int IsOpen;
	}

	private sealed record LoadRequest(string? InputPath, OmrEngine Engine, bool BypassKnownFailure, RecentSongEntry? RecentSong, bool ForceReprocess = false, bool ReuseConfirmed = false)
	{
		public string DisplayName => RecentSong?.DisplayName ?? Path.GetFileName(InputPath ?? "Sheet music");
	}

	private enum ReuseAction
	{
		None,
		UseCached,
		Reprocess,
		Cancel
	}

	private enum ErrorAction
	{
		None,
		RetrySame,
		RetryAlternate,
		ChooseFile,
		Back
	}

	private const int InitialWidth = 1280;

	private const int InitialHeight = 720;

	private const int MinimumWidth = 960;

	private const int MinimumHeight = 540;

	public static int Main(string[] args)
	{
		if (args.Length > 0 && string.Equals(args[0], "--smoke", StringComparison.OrdinalIgnoreCase))
		{
			string outputDirectory = ((args.Length > 1)
				? args[1]
				: Path.Combine(Path.GetTempPath(), "sheet2play-smoke"));
			return RunSmoke(outputDirectory);
		}
		if (args.Length > 0 && string.Equals(args[0], "--smoke-gif", StringComparison.OrdinalIgnoreCase))
		{
			return RunDemoGif(args);
		}
		if (args.Length > 0 && string.Equals(args[0], "--reconvert", StringComparison.OrdinalIgnoreCase))
		{
			return RunReconvert(args);
		}
		if (args.Length > 0 && string.Equals(args[0], "--render-audio", StringComparison.OrdinalIgnoreCase))
		{
			return RunRenderAudio(args);
		}
		RunApplication();
		return 0;
	}

	/// <summary>
	/// Re-runs recognition over every cached song whose source is still in the library.
	/// </summary>
	/// <remarks>
	/// Caches are keyed on the engine revision, so bumping it invalidates every entry and the
	/// songs would otherwise reconvert one at a time as the user opened them. This does the
	/// whole set up front, unattended, through the same <see cref="SongCache.LoadOrCreateDetailed"/>
	/// path the app uses - so the caches produced are identical to normal ones, rather than
	/// something written by a parallel implementation that could drift.
	/// </remarks>
	private static int RunReconvert(string[] args)
	{
		OmrEngine engine = OmrEngine.Homr;
		if (args.Length > 1 && Enum.TryParse(args[1], ignoreCase: true, out OmrEngine parsed))
		{
			engine = parsed;
		}

		IReadOnlyList<PdfLibraryEntry> library = SongCache.GetPdfLibrary();
		Console.WriteLine($"Re-converting {library.Count} source file(s) with {OmrPipeline.GetEngineName(engine)}");
		Console.WriteLine($"engine revision: {OmrPipeline.GetEngineRevision(engine)}");
		Console.WriteLine();

		int converted = 0;
		int failed = 0;
		for (int index = 0; index < library.Count; index++)
		{
			PdfLibraryEntry entry = library[index];
			string label = $"[{index + 1}/{library.Count}] {entry.DisplayName}";
			try
			{
				// forceReprocess so a still-valid cache is rebuilt too; bypassKnownFailure so a
				// remembered failure from an older engine does not skip a file this one may handle.
				SongLoadResult result = SongCache.LoadOrCreateDetailed(
					entry.FullPath,
					engine,
					bypassKnownFailure: true,
					forceReprocess: true);
				converted++;
				Console.WriteLine($"{label}: OK, {result.NoteCount} notes");
			}
			catch (Exception error)
			{
				failed++;
				Console.WriteLine($"{label}: FAILED - {error.Message}");
			}
		}

		Console.WriteLine();
		Console.WriteLine($"converted {converted}, failed {failed}");
		return failed == 0 ? 0 : 1;
	}

	private static void RunApplication()
	{
		Application.EnableVisualStyles();
		Application.SetCompatibleTextRenderingDefault(defaultValue: false);
		// VSyncHint locks presentation to the display's scanout. Without it the frame
		// limiter below free-runs at almost-but-not-exactly the refresh rate, and the
		// resulting tear seam crawls steadily up the window - most visible once
		// playback stops and the seam is the only thing still moving.
		Raylib.SetConfigFlags(ConfigFlags.ResizableWindow | ConfigFlags.VSyncHint);
		Raylib.InitWindow(1280, 720, "Sheet2Play");
		Raylib.SetWindowMinSize(960, 540);
		// Kept as a ceiling for drivers that override the vsync hint.
		Raylib.SetTargetFPS(144);
		UiTheme.InitializeFonts();
		AudioBackend preferredBackend = AppSettingsStore.LoadAudioBackend();
		selectedAudioBackend = preferredBackend;
		// The built-in synth loads a soundfont from disk in well under a second; opening a cold
		// VirtualMIDISynth makes it page in gigabytes of samples and takes seconds. Say which is
		// happening, because a silent multi-second stall reads as a hang.
		DrawStartupNotice(preferredBackend == AudioBackend.SoundFont
			? "Loading soundfont..."
			: "Connecting to audio device...");
		using AudioOutput audioOutput = AudioOutput.Create(
			preferredBackend,
			AppSettingsStore.LoadSoundFontPath());
		IMidiOutput midiOutput = audioOutput.MidiOutput;
		string audioWarning = audioOutput.Status.Problem;
		// Set after Create, not from the setting: Create falls back when the preferred backend
		// cannot be opened, and the offset must be saved against what is actually playing.
		activeAudioBackend = audioOutput.Backend;
		activeAudioStatus = audioOutput.Status;
		UiLayout layout = UiLayout.Create(Raylib.GetScreenWidth(), Raylib.GetScreenHeight());
		Keyboard keyboard = new Keyboard(layout.Width, layout.HitLineY, layout.KeyboardHeight);
		int lastWidth = layout.Width;
		int lastHeight = layout.Height;
		ConcurrentQueue<string> selectedFiles = new ConcurrentQueue<string>();
		ConcurrentQueue<LoadRequest> loadRequests = new ConcurrentQueue<LoadRequest>();
		LoadResultHandoff<SongLoadResult> loadResults = new LoadResultHandoff<SongLoadResult>();
		LoadProgressTracker progressQueue = new LoadProgressTracker();
		LoadProgressModel loadProgressModel = new LoadProgressModel();
		using CancellationTokenSource applicationLifetime = new CancellationTokenSource();
		CancellationTokenSource cancellationTokenSource = null;
		Task task = null;
		DialogState dialogState = new DialogState();
		GameState state = GameState.WaitingForFile;
		OmrEngine selectedEngine = AppSettingsStore.LoadEngine();
		LoadRequest pendingRequest = null;
		PlaybackController playbackController = null;
		SongLoadResult songLoadResult = null;
		Exception exception = null;
		string message = audioWarning;
		IReadOnlyList<PdfLibraryEntry> pdfLibrary = SongCache.GetPdfLibrary();
		IReadOnlyList<CachedSongEntry> cachedSongs = SongCache.GetCachedSongs();
		int pdfScrollOffset = 0;
		int cacheScrollOffset = 0;
		OmrEngine? cacheEngineFilter = null;
		IReadOnlyList<MidiLibraryEntry> midiLibrary = SongCache.GetMidiLibrary();
		int midiScrollOffset = 0;
		LibrarySearchState librarySearch = new LibrarySearchState();
		bool sliderDragging = false;
		bool resumeAfterSlider = false;
		double sliderPreviewPosition = 0.0;
		PlaybackRateEditor playbackRateEditor = new PlaybackRateEditor();
		AudioOffsetEditor audioOffsetEditor = new AudioOffsetEditor();
		while (!Raylib.WindowShouldClose())
		{
			if (Raylib.IsKeyPressed(KeyboardKey.F11))
			{
				Raylib.ToggleFullscreen();
			}
			int screenWidth = Raylib.GetScreenWidth();
			int screenHeight = Raylib.GetScreenHeight();
			if (screenWidth != lastWidth || screenHeight != lastHeight)
			{
				layout = UiLayout.Create(screenWidth, screenHeight);
				keyboard.Resize(layout.Width, layout.HitLineY, layout.KeyboardHeight);
				lastWidth = screenWidth;
				lastHeight = screenHeight;
			}
			// Before anything else, and on every screen rather than only while playing: the
			// built-in synth's stream must never run dry, or resuming clicks, and song time is
			// re-anchored here so Update() below reads a fresh position rather than a stale one.
			audioOutput.Pump();
			OmrProgress progress;
			while (progressQueue.TryTake(out progress) && progress is not null)
			{
				loadProgressModel.Apply(progress);
			}
			if (loadResults.TryTake(out LoadCompletion<SongLoadResult> completion) && completion is not null)
			{
				cancellationTokenSource?.Dispose();
				cancellationTokenSource = null;
				task = null;
				loadProgressModel.Stop();
				if (completion.Error is OperationCanceledException)
				{
					message = "Conversion cancelled. No partial cache was saved.";
					exception = null;
					state = GameState.WaitingForFile;
				}
				else if (completion.Error != null)
				{
					Console.Error.WriteLine("[BACKGROUND TASK FAILED]");
					Console.Error.WriteLine(completion.Error);
					exception = completion.Error;
					state = GameState.Error;
				}
				else
				{
					SongLoadResult value = completion.Value;
					if (value is not null)
					{
						List<Note> notes = value.Notes;
						if (notes != null && notes.Count > 0)
						{
							playbackController?.Stop();
							songLoadResult = value;
							// The offset means different things per backend - a dispatch lead for
							// an external synth, an output latency for the built-in one - so it is
							// resolved per backend rather than shared.
							double offsetSeconds = AppSettingsStore.ResolveAudioOffsetMilliseconds(
								audioOutput.Backend, audioOutput.BufferedSeconds) / 1000.0;
							PlaybackSession newSession = new(value.Notes, offsetSeconds);
							playbackController = new PlaybackController(
								newSession,
								midiOutput,
								audioOutput.CreateTimebase(newSession, offsetSeconds));
							playbackRateEditor.Cancel();
							sliderDragging = false;
							exception = null;
							message = null;
							pdfLibrary = SongCache.GetPdfLibrary();
							cachedSongs = SongCache.GetCachedSongs();
							midiLibrary = SongCache.GetMidiLibrary();
							state = GameState.Playing;
						}
					}
				}
			}
			HandleDroppedFiles(state, selectedFiles);
			string result;
			while (state == GameState.WaitingForFile && selectedFiles.TryDequeue(out result))
			{
				loadRequests.Enqueue(new LoadRequest(result, selectedEngine, BypassKnownFailure: false, null));
			}
			// A load is only picked up from the idle screens; mid-conversion or mid-playback
			// the queue is left alone until the user comes back to the library.
			bool canStartLoad = state is GameState.WaitingForFile or GameState.Error;
			if (canStartLoad && loadRequests.TryDequeue(out var request))
			{
				pendingRequest = request;
				exception = null;
				message = null;
				if (NeedsReuseConfirmation(request))
				{
					state = GameState.ConfirmReuse;
				}
				else
				{
					loadProgressModel.Start(request.DisplayName, request.Engine);
					cancellationTokenSource = CancellationTokenSource.CreateLinkedTokenSource(applicationLifetime.Token);
					CancellationToken token = cancellationTokenSource.Token;
					state = GameState.Processing;
					task = Task.Run(delegate
					{
						LoadSong(request, loadResults, progressQueue, token);
					});
				}
			}
			if (playbackController != null && state is GameState.Playing or GameState.Completed)
			{
				HandlePlaybackKeyboard(playbackController, playbackRateEditor, ref state, ref sliderDragging, ref resumeAfterSlider, ref sliderPreviewPosition, layout);
				if (!playbackRateEditor.IsEditing && !audioOffsetEditor.IsEditing && !sliderDragging)
				{
					int offsetStep = 0;
					if (Raylib.IsKeyPressed(KeyboardKey.LeftBracket))
					{
						offsetStep = -AudioOffsetRules.StepMilliseconds;
					}
					else if (Raylib.IsKeyPressed(KeyboardKey.RightBracket))
					{
						offsetStep = AudioOffsetRules.StepMilliseconds;
					}
					if (offsetStep != 0)
					{
						StepAudioOffset(playbackController, offsetStep);
					}
				}
				playbackController.Update();
				if (playbackController.IsCompleted)
				{
					state = GameState.Completed;
				}
			}
			Raylib.BeginDrawing();
			Raylib.ClearBackground(UiTheme.Background);
			switch (state)
			{
			case GameState.WaitingForFile:
			{
				bool browseRequested;
				bool refreshRequested;
				LoadRequest loadRequest = DrawLanding(layout, ref selectedEngine, pdfLibrary, cachedSongs, midiLibrary, ref pdfScrollOffset, ref cacheScrollOffset, ref cacheEngineFilter, ref midiScrollOffset, librarySearch, message, out browseRequested, out refreshRequested);
				if (browseRequested || (!librarySearch.IsTyping && Raylib.IsKeyPressed(KeyboardKey.B)))
				{
					StartFilePicker(selectedFiles, dialogState);
				}
				if (refreshRequested)
				{
					pdfLibrary = SongCache.GetPdfLibrary();
					cachedSongs = SongCache.GetCachedSongs();
					midiLibrary = SongCache.GetMidiLibrary();
					pdfScrollOffset = 0;
					cacheScrollOffset = 0;
					midiScrollOffset = 0;
				}
				if (loadRequest is not null)
				{
					loadRequests.Enqueue(loadRequest);
				}
				break;
			}
			case GameState.ConfirmReuse:
			{
				ReuseAction reuseAction = DrawConfirmReuse(layout, pendingRequest);
				if (Raylib.IsKeyPressed(KeyboardKey.Escape))
				{
					reuseAction = ReuseAction.Cancel;
				}
				HandleReuseAction(reuseAction, pendingRequest, loadRequests, ref state);
				break;
			}
			case GameState.Processing:
				if (DrawProcessing(layout, loadProgressModel, cancelling: false) || Raylib.IsKeyPressed(KeyboardKey.Escape))
				{
					cancellationTokenSource?.Cancel();
					state = GameState.Cancelling;
				}
				break;
			case GameState.Cancelling:
				DrawProcessing(layout, loadProgressModel, cancelling: true);
				break;
			case GameState.Error:
				HandleErrorAction(DrawError(layout, exception, pendingRequest), pendingRequest, selectedFiles, dialogState, loadRequests, ref state);
				break;
			case GameState.Playing:
			case GameState.Completed:
				if (playbackController != null && songLoadResult is not null && DrawPlayback(playbackController, songLoadResult, keyboard, sliderDragging, sliderPreviewPosition, playbackRateEditor, audioOffsetEditor, ref state, layout))
				{
					playbackController.Stop();
					playbackRateEditor.Cancel();
					state = GameState.WaitingForFile;
				}
				break;
			}
			Raylib.EndDrawing();
		}
		applicationLifetime.Cancel();
		cancellationTokenSource?.Cancel();
		if (task != null)
		{
			try
			{
				task.Wait(TimeSpan.FromSeconds(5L));
			}
			catch (AggregateException ex) when (ex.InnerExceptions.All((Exception item) => item is OperationCanceledException))
			{
			}
		}
		cancellationTokenSource?.Dispose();
		playbackController?.Stop();
		midiOutput.AllNotesOff();
		UiTheme.ShutdownFonts();
		Raylib.CloseWindow();
	}

	/// <summary>
	/// Presents a single frame so the window has painted before a slow blocking call.
	/// </summary>
	/// <remarks>
	/// Opening the MIDI device makes the synthesiser load its sound bank, and a large one -
	/// several gigabytes of piano samples for VirtualMIDISynth here - takes long enough that
	/// Windows marks the process Not Responding. The window is created by InitWindow before
	/// that happens, so without this the user sees a blank white rectangle and reasonably
	/// concludes the app has hung. It only looks that way on a cold synthesiser: once the
	/// samples are resident the next open returns immediately, which is why closing and
	/// relaunching appears to fix it.
	///
	/// This does not shorten the wait. It replaces an unexplained freeze with a window that
	/// says what it is doing. Do not remove it because a lone draw before the main loop looks
	/// redundant.
	/// </remarks>
	private static void DrawStartupNotice(string message)
	{
		Raylib.BeginDrawing();
		Raylib.ClearBackground(UiTheme.Background);
		int fontSize = 20;
		int x = (Raylib.GetScreenWidth() - UiTheme.MeasureText(message, fontSize)) / 2;
		int y = Raylib.GetScreenHeight() / 2 - fontSize;
		UiTheme.DrawText(message, x, y, fontSize, UiTheme.Text);

		const string hint = "First launch can take a moment while the synthesiser loads its sounds.";
		int hintSize = 14;
		int hintX = (Raylib.GetScreenWidth() - UiTheme.MeasureText(hint, hintSize)) / 2;
		UiTheme.DrawText(hint, hintX, y + fontSize + 14, hintSize, UiTheme.Muted);
		Raylib.EndDrawing();
	}

	private unsafe static void StartFilePicker(ConcurrentQueue<string> selectedFiles, DialogState dialogState)
	{
		ConcurrentQueue<string> selectedFiles2 = selectedFiles;
		DialogState dialogState2 = dialogState;
		if (Interlocked.CompareExchange(ref dialogState2.IsOpen, 1, 0) != 0)
		{
			return;
		}
		nint ownerHandle = (nint)Raylib.GetWindowHandle();
		Thread thread = new Thread((ThreadStart)delegate
		{
			try
			{
				OpenFileDialog openFileDialog = new OpenFileDialog
				{
					Filter = "Sheet Music & MIDI|*.bmp;*.jpeg;*.jpg;*.pdf;*.png;*.tif;*.tiff;*.webp;*.mid;*.midi;*.mxl;*.musicxml;*.xml"
				};
				try
				{
					if (((ownerHandle == IntPtr.Zero) ? openFileDialog.ShowDialog() : openFileDialog.ShowDialog(new Win32Window(ownerHandle))) == DialogResult.OK)
					{
						selectedFiles2.Enqueue(openFileDialog.FileName);
					}
				}
				finally
				{
					((IDisposable)(object)openFileDialog)?.Dispose();
				}
			}
			finally
			{
				Interlocked.Exchange(ref dialogState2.IsOpen, 0);
			}
		});
		thread.SetApartmentState(ApartmentState.STA);
		thread.Start();
	}

	private unsafe static void HandleDroppedFiles(GameState state, ConcurrentQueue<string> selectedFiles)
	{
		if (state != 0 || !Raylib.IsFileDropped())
		{
			return;
		}
		FilePathList files = Raylib.LoadDroppedFiles();
		try
		{
			if (files.Count != 0)
			{
				string text = Marshal.PtrToStringUTF8((nint)(*files.Paths));
				if (!string.IsNullOrWhiteSpace(text))
				{
					selectedFiles.Enqueue(text);
				}
			}
		}
		finally
		{
			Raylib.UnloadDroppedFiles(files);
		}
	}

	private static void LoadSong(LoadRequest request, LoadResultHandoff<SongLoadResult> results, LoadProgressTracker progress, CancellationToken cancellationToken)
	{
		try
		{
			SongLoadResult value = ((request.RecentSong is not null) ? SongCache.LoadRecent(request.RecentSong) : SongCache.LoadOrCreateDetailed(request.InputPath ?? throw new InvalidOperationException("Load request has no source path."), request.Engine, cancellationToken, progress, request.BypassKnownFailure, request.ForceReprocess));
			results.Complete(value);
		}
		catch (Exception error)
		{
			results.Fail(error);
		}
	}

	/// <summary>
	/// True when this request would silently reuse an existing cache, so the user should be
	/// asked first. Cache-playlist replays and direct MIDI/MusicXML loads never ask, because
	/// neither runs the OMR pipeline.
	/// </summary>
	private static bool NeedsReuseConfirmation(LoadRequest request)
	{
		if (request.ReuseConfirmed || request.ForceReprocess || request.RecentSong is not null)
		{
			return false;
		}
		string? inputPath = request.InputPath;
		if (string.IsNullOrWhiteSpace(inputPath))
		{
			return false;
		}
		if (Path.GetExtension(inputPath).ToLowerInvariant() is ".mid" or ".midi" or ".mxl" or ".musicxml" or ".xml")
		{
			return false;
		}
		return SongCache.HasCachedResult(inputPath, request.Engine);
	}

	private static ReuseAction DrawConfirmReuse(UiLayout layout, LoadRequest? request)
	{
		if (request is null)
		{
			return ReuseAction.Cancel;
		}
		float scale = layout.Scale;
		float width = Math.Min((float)layout.Width - 64f * scale, 760f * scale);
		float height = 250f * scale;
		Rectangle bounds = new Rectangle(((float)layout.Width - width) / 2f, ((float)layout.Height - height) / 2f, width, height);
		UiTheme.DrawCard(bounds, scale);
		string engineName = OmrPipeline.GetEngineName(request.Engine).ToUpperInvariant();
		UiTheme.DrawText("Already converted", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 26f * scale), Math.Max(24, (int)(30f * scale)), UiTheme.Warning);
		DrawWrappedText($"\"{request.DisplayName}\" already has a validated {engineName} cache, so it would load instantly. Re-running replaces that cache and takes the full {engineName} conversion time.", new Rectangle(bounds.X + 30f * scale, bounds.Y + 84f * scale, bounds.Width - 60f * scale, 84f * scale), Math.Max(14, (int)(17f * scale)), UiTheme.Text);
		float y = bounds.Y + bounds.Height - 74f * scale;
		float gap = 10f * scale;
		float buttonWidth = (bounds.Width - 60f * scale - gap * 2f) / 3f;
		if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale, y, buttonWidth, 44f * scale), "Use cached", UiTheme.Lime))
		{
			return ReuseAction.UseCached;
		}
		if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale + buttonWidth + gap, y, buttonWidth, 44f * scale), "Re-run " + engineName, UiTheme.Warning))
		{
			return ReuseAction.Reprocess;
		}
		if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale + (buttonWidth + gap) * 2f, y, buttonWidth, 44f * scale), "Cancel", UiTheme.Sky))
		{
			return ReuseAction.Cancel;
		}
		return ReuseAction.None;
	}

	private static void HandleReuseAction(ReuseAction action, LoadRequest? request, ConcurrentQueue<LoadRequest> loadRequests, ref GameState state)
	{
		switch (action)
		{
		case ReuseAction.UseCached:
			if (request is not null)
			{
				loadRequests.Enqueue(request with { ReuseConfirmed = true });
			}
			state = GameState.WaitingForFile;
			break;
		case ReuseAction.Reprocess:
			if (request is not null)
			{
				loadRequests.Enqueue(request with { ForceReprocess = true, ReuseConfirmed = true });
			}
			state = GameState.WaitingForFile;
			break;
		case ReuseAction.Cancel:
			state = GameState.WaitingForFile;
			break;
		}
	}

	private static LoadRequest? DrawLanding(UiLayout layout, ref OmrEngine selectedEngine, IReadOnlyList<PdfLibraryEntry> pdfLibrary, IReadOnlyList<CachedSongEntry> cachedSongs, IReadOnlyList<MidiLibraryEntry> midiLibrary, ref int pdfScrollOffset, ref int cacheScrollOffset, ref OmrEngine? cacheEngineFilter, ref int midiScrollOffset, LibrarySearchState librarySearch, string? message, out bool browseRequested, out bool refreshRequested)
	{
		float scale = layout.Scale;
		int fontSize = Math.Max(25, (int)(34f * scale));
		UiTheme.DrawText("Sheet2Play", (int)(32f * scale), (int)(18f * scale), fontSize, UiTheme.Text);
		UiTheme.DrawText("Turn sheet music into synchronized piano playback", (int)(34f * scale), (int)(56f * scale), Math.Max(13, (int)(16f * scale)), UiTheme.Muted);
		UiTheme.DrawText("F11  FULLSCREEN", layout.Width - (int)(150f * scale), (int)(29f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		float contentWidth = Math.Min((float)layout.Width - 48f * scale, 1120f * scale);
		float contentLeft = ((float)layout.Width - contentWidth) / 2f;
		Rectangle bounds = new Rectangle(contentLeft, 88f * scale, contentWidth, 74f * scale);
		UiTheme.DrawCard(bounds, scale);
		UiTheme.DrawText("Drop a PDF or score image here", (int)(bounds.X + 24f * scale), (int)(bounds.Y + 14f * scale), Math.Max(16, (int)(20f * scale)), UiTheme.Text);
		UiTheme.DrawText("PDF, PNG, JPEG, TIFF, BMP or WebP", (int)(bounds.X + 24f * scale), (int)(bounds.Y + 43f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		Rectangle browseButton = new Rectangle(bounds.X + bounds.Width - 150f * scale, bounds.Y + 16f * scale, 122f * scale, 42f * scale);
		browseRequested = UiTheme.DrawButton(browseButton, "Browse", UiTheme.Sky);
		Rectangle refreshButton = new Rectangle(browseButton.X - 112f * scale, browseButton.Y, 98f * scale, browseButton.Height);
		refreshRequested = UiTheme.DrawButton(refreshButton, "Refresh", UiTheme.Muted);
		UiTheme.DrawText("OMR ENGINE", (int)contentLeft, (int)(174f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		float engineCardGap = 16f * scale;
		float engineCardWidth = (contentWidth - engineCardGap) / 2f;
		Rectangle zeusCard = new Rectangle(contentLeft, 194f * scale, engineCardWidth, 64f * scale);
		Rectangle homrCard = new Rectangle(contentLeft + engineCardWidth + engineCardGap, 194f * scale, engineCardWidth, 64f * scale);
		if (DrawEngineCard(zeusCard, "Zeus GPU", "Experimental rhythm · CUDA-only", UiTheme.Sky, selectedEngine == OmrEngine.Zeus))
		{
			selectedEngine = OmrEngine.Zeus;
			PersistEngine(selectedEngine);
		}
		if (DrawEngineCard(homrCard, "homr", "Faster · general sheet music", UiTheme.Lime, selectedEngine == OmrEngine.Homr))
		{
			selectedEngine = OmrEngine.Homr;
			PersistEngine(selectedEngine);
		}
		// Gated on focus: these would otherwise fire on the o and h in a typed query.
		if (!librarySearch.IsTyping && Raylib.IsKeyPressed(KeyboardKey.O))
		{
			selectedEngine = OmrEngine.Zeus;
			PersistEngine(selectedEngine);
		}
		else if (!librarySearch.IsTyping && Raylib.IsKeyPressed(KeyboardKey.H))
		{
			selectedEngine = OmrEngine.Homr;
			PersistEngine(selectedEngine);
		}
		// AUDIO OUTPUT sits between the engine row and the library panels. The backend is a
		// user-adjustable setting, so it gets a visible control rather than only a shortcut.
		UiTheme.DrawText("AUDIO OUTPUT", (int)contentLeft, (int)(274f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		Rectangle synthCard = new Rectangle(contentLeft, 294f * scale, engineCardWidth, 64f * scale);
		Rectangle deviceCard = new Rectangle(contentLeft + engineCardWidth + engineCardGap, 294f * scale, engineCardWidth, 64f * scale);
		int audioDescriptionSize = Math.Max(12, (int)(14f * scale));
		int audioDescriptionWidth = (int)(engineCardWidth - 60f * scale);
		// The dot follows the stored choice so clicking responds, but the description tells the
		// truth about what is playing: switching backend means reopening an audio device, so it
		// applies at the next launch rather than mid-song.
		string synthDescription = selectedAudioBackend != activeAudioBackend && selectedAudioBackend == AudioBackend.SoundFont
			? "Restart to apply"
			: activeAudioStatus?.SoundFontName is string fontName
				? UiTheme.Ellipsize(fontName, audioDescriptionSize, audioDescriptionWidth) + " · reverb"
				: "No soundfont installed";
		string deviceDescription = selectedAudioBackend != activeAudioBackend && selectedAudioBackend == AudioBackend.MidiDevice
			? "Restart to apply"
			: activeAudioStatus?.DeviceName is string deviceName
				? UiTheme.Ellipsize(deviceName, audioDescriptionSize, audioDescriptionWidth) + " · external"
				// Only claim there is no device when we actually went looking. With the built-in
				// synth playing, the MIDI device is never opened, so its absence is unknown
				// rather than established.
				: activeAudioBackend == AudioBackend.MidiDevice
					? "No MIDI device found"
					: "VirtualMIDISynth or similar";
		if (DrawEngineCard(synthCard, "Built-in synth", synthDescription, UiTheme.Lime, selectedAudioBackend == AudioBackend.SoundFont))
		{
			PersistAudioBackend(AudioBackend.SoundFont);
		}
		if (DrawEngineCard(deviceCard, "MIDI device", deviceDescription, UiTheme.Sky, selectedAudioBackend == AudioBackend.MidiDevice))
		{
			PersistAudioBackend(AudioBackend.MidiDevice);
		}
		float panelsTop = 374f * scale;
		float panelGap = 14f * scale;
		float panelWidth = (contentWidth - 2 * panelGap) / 3f;
		float height = Math.Max(170f * scale, (float)layout.Height - panelsTop - 24f * scale);
		Rectangle pdfPanel = new Rectangle(contentLeft, panelsTop, panelWidth, height);
		Rectangle cachePanel = new Rectangle(contentLeft + panelWidth + panelGap, panelsTop, panelWidth, height);
		Rectangle midiPanel = new Rectangle(contentLeft + 2 * (panelWidth + panelGap), panelsTop, panelWidth, height);
		PdfLibraryEntry pdfLibraryEntry = DrawPdfLibraryPanel(pdfPanel, pdfLibrary, ref pdfScrollOffset, librarySearch, scale);
		CachedSongEntry cachedSongEntry = DrawCacheLibraryPanel(cachePanel, cachedSongs, ref cacheScrollOffset, ref cacheEngineFilter, librarySearch, scale);
		MidiLibraryEntry midiLibraryEntry = DrawMidiLibraryPanel(midiPanel, midiLibrary, ref midiScrollOffset, librarySearch, scale);
		if (!string.IsNullOrWhiteSpace(message))
		{
			Rectangle messageBar = new Rectangle(contentLeft + 8f * scale, (float)layout.Height - 47f * scale, contentWidth - 16f * scale, 32f * scale);
			Raylib.DrawRectangleRounded(messageBar, 0.18f, 8, UiTheme.Elevated);
			UiTheme.DrawText(UiTheme.Ellipsize(message, 13, (int)(messageBar.Width - 20f * scale)), (int)(messageBar.X + 10f * scale), (int)(messageBar.Y + 8f * scale), 13, UiTheme.Warning);
		}
		if (pdfLibraryEntry is not null)
		{
			return new LoadRequest(pdfLibraryEntry.FullPath, selectedEngine, BypassKnownFailure: false, null);
		}
		if (cachedSongEntry is not null)
		{
			return new LoadRequest(null, cachedSongEntry.RecentSong.Engine, BypassKnownFailure: false, cachedSongEntry.RecentSong);
		}
		if (midiLibraryEntry is not null)
		{
			return new LoadRequest(midiLibraryEntry.FullPath, selectedEngine, BypassKnownFailure: false, null);
		}
		return null;
	}

	private static PdfLibraryEntry? DrawPdfLibraryPanel(Rectangle panel, IReadOnlyList<PdfLibraryEntry> entries, ref int scrollOffset, LibrarySearchState search, float scale)
	{
		string query = search.Get(LibraryColumn.Pdf);
		IReadOnlyList<PdfLibraryEntry> matches = FilterLibrary(entries, query, static entry => entry.DisplayName);
		DrawLibraryHeader(panel, "PDF LIBRARY", FormatLibraryCount(entries.Count, matches.Count, "files"), UiTheme.Sky, scale);
		if (DrawLibrarySearchBox(panel, LibraryColumn.Pdf, search, scale))
		{
			scrollOffset = 0;
		}
		entries = matches;
		int visibleLibraryRows = GetVisibleLibraryRows(panel, scale);
		UpdateLibraryScroll(panel, entries.Count, visibleLibraryRows, ref scrollOffset);
		PdfLibraryEntry result = null;
		float rowHeight = Math.Clamp(48f * scale, 40f, 58f);
		float rowGap = Math.Clamp(6f * scale, 4f, 9f);
		float rowsTop = panel.Y + LibraryRowsTop * scale;
		for (int index = 0; index < visibleLibraryRows && scrollOffset + index < entries.Count; index++)
		{
			PdfLibraryEntry pdfLibraryEntry = entries[scrollOffset + index];
			Rectangle row = new Rectangle(panel.X + 10f * scale, rowsTop + (float)index * (rowHeight + rowGap), panel.Width - 20f * scale, rowHeight);
			Raylib.DrawRectangleRounded(row, 0.12f, 8, UiTheme.Elevated);
			int fontSize = Math.Max(12, (int)(15f * scale));
			UiTheme.DrawText(UiTheme.Ellipsize(pdfLibraryEntry.DisplayName, fontSize, (int)(row.Width - 94f * scale)), (int)(row.X + 12f * scale), (int)(row.Y + 7f * scale), fontSize, UiTheme.Text);
			UiTheme.DrawText(FormatFileSize(pdfLibraryEntry.SizeBytes), (int)(row.X + 12f * scale), (int)(row.Y + 27f * scale), Math.Max(10, (int)(12f * scale)), UiTheme.Muted);
			if (UiTheme.DrawButton(new Rectangle(row.X + row.Width - 72f * scale, row.Y + 7f * scale, 62f * scale, row.Height - 14f * scale), "Load", UiTheme.Sky))
			{
				result = pdfLibraryEntry;
			}
		}
		if (entries.Count == 0)
		{
			DrawLibraryEmpty(panel, string.IsNullOrWhiteSpace(query) ? "Put PDF files in songs/pdf" : $"No PDF matches \"{query}\"", scale);
		}
		DrawLibraryScrollbar(panel, entries.Count, visibleLibraryRows, scrollOffset, scale);
		return result;
	}


	private static MidiLibraryEntry? DrawMidiLibraryPanel(Rectangle panel, IReadOnlyList<MidiLibraryEntry> entries, ref int scrollOffset, LibrarySearchState search, float scale)
	{
		string query = search.Get(LibraryColumn.Midi);
		IReadOnlyList<MidiLibraryEntry> matches = FilterLibrary(entries, query, static entry => entry.DisplayName);
		DrawLibraryHeader(panel, "MIDI PLAYER", FormatLibraryCount(entries.Count, matches.Count, "tracks"), UiTheme.Sky, scale);
		if (DrawLibrarySearchBox(panel, LibraryColumn.Midi, search, scale))
		{
			scrollOffset = 0;
		}
		entries = matches;
		int visibleLibraryRows = GetVisibleLibraryRows(panel, scale);
		UpdateLibraryScroll(panel, entries.Count, visibleLibraryRows, ref scrollOffset);
		MidiLibraryEntry result = null;
		float rowHeight = Math.Clamp(48f * scale, 40f, 58f);
		float rowGap = Math.Clamp(6f * scale, 4f, 9f);
		float rowsTop = panel.Y + LibraryRowsTop * scale;
		for (int index = 0; index < visibleLibraryRows && scrollOffset + index < entries.Count; index++)
		{
			MidiLibraryEntry entry = entries[scrollOffset + index];
			Rectangle row = new Rectangle(panel.X + 10f * scale, rowsTop + (float)index * (rowHeight + rowGap), panel.Width - 20f * scale, rowHeight);
			Raylib.DrawRectangleRounded(row, 0.12f, 8, UiTheme.Elevated);
			int fontSize = Math.Max(12, (int)(15f * scale));
			UiTheme.DrawText(UiTheme.Ellipsize(entry.DisplayName, fontSize, (int)(row.Width - 94f * scale)), (int)(row.X + 12f * scale), (int)(row.Y + 7f * scale), fontSize, UiTheme.Text);
			UiTheme.DrawText(FormatFileSize(entry.SizeBytes), (int)(row.X + 12f * scale), (int)(row.Y + 27f * scale), Math.Max(10, (int)(12f * scale)), UiTheme.Muted);
			if (UiTheme.DrawButton(new Rectangle(row.X + row.Width - 72f * scale, row.Y + 7f * scale, 62f * scale, row.Height - 14f * scale), "Play", UiTheme.Sky))
			{
				result = entry;
			}
		}
		if (entries.Count == 0)
		{
			DrawLibraryEmpty(panel, string.IsNullOrWhiteSpace(query) ? "Put MIDI/MXL files in songs/midi/custom" : $"No track matches \"{query}\"", scale);
		}
		DrawLibraryScrollbar(panel, entries.Count, visibleLibraryRows, scrollOffset, scale);
		return result;
	}

	private static CachedSongEntry? DrawCacheLibraryPanel(Rectangle panel, IReadOnlyList<CachedSongEntry> entries, ref int scrollOffset, ref OmrEngine? engineFilter, LibrarySearchState search, float scale)
	{
		string query = search.Get(LibraryColumn.Cache);
		IReadOnlyList<CachedSongEntry> matches = FilterLibrary(entries, query, static entry => entry.RecentSong.DisplayName);
		DrawLibraryHeader(panel, "CACHE PLAYLIST", FormatLibraryCount(entries.Count, matches.Count, "ready"), UiTheme.Lime, scale);
		if (entries.Count == 0)
		{
			DrawLibraryEmpty(panel, "Validated MIDI caches appear here", scale);
			scrollOffset = 0;
			engineFilter = null;
			return null;
		}
		if (DrawLibrarySearchBox(panel, LibraryColumn.Cache, search, scale))
		{
			scrollOffset = 0;
		}
		// The engine tabs count what the search left, so their numbers match the rows.
		entries = matches;
		if (entries.Count == 0)
		{
			DrawLibraryEmpty(panel, $"No cached song matches {query}", scale);
			scrollOffset = 0;
			return null;
		}
		OmrEngine[] presentEngines = entries
			.Select(static entry => entry.RecentSong.Engine)
			.Distinct()
			.OrderBy(static engine => (int)engine)
			.ToArray();
		if (engineFilter.HasValue && !presentEngines.Contains(engineFilter.Value))
		{
			engineFilter = null;
			scrollOffset = 0;
		}
		if (DrawEngineTabs(panel, presentEngines, entries, ref engineFilter, scale))
		{
			scrollOffset = 0;
		}
		OmrEngine? activeFilter = engineFilter;
		IReadOnlyList<CachedSongEntry> visible = activeFilter.HasValue
			? entries.Where(entry => entry.RecentSong.Engine == activeFilter.Value).ToArray()
			: entries;
		float rowsTop = CacheRowsTop;
		float rowHeight = Math.Clamp(48f * scale, 40f, 58f);
		float rowGap = Math.Clamp(6f * scale, 4f, 9f);
		float headerHeight = Math.Clamp(22f * scale, 18f, 28f);
		float available = panel.Height - (rowsTop + 8f) * scale;
		List<(OmrEngine Engine, CachedSongEntry? Entry)> rows = BuildCacheRows(visible, !activeFilter.HasValue);
		int visibleRows = CountVisibleCacheRows(rows, scrollOffset, available, rowHeight, rowGap, headerHeight);
		UpdateLibraryScroll(panel, rows.Count, visibleRows, ref scrollOffset);
		visibleRows = CountVisibleCacheRows(rows, scrollOffset, available, rowHeight, rowGap, headerHeight);
		CachedSongEntry result = null;
		float y = panel.Y + rowsTop * scale;
		for (int i = scrollOffset; i < rows.Count && i < scrollOffset + visibleRows; i++)
		{
			(OmrEngine engine, CachedSongEntry? entry) = rows[i];
			Color accent = GetEngineAccent(engine);
			if (entry == null)
			{
				UiTheme.DrawText(OmrPipeline.GetEngineName(engine).ToUpperInvariant(), (int)(panel.X + 14f * scale), (int)(y + 5f * scale), Math.Max(10, (int)(11f * scale)), accent);
				y += headerHeight + rowGap;
				continue;
			}
			Rectangle rec = new Rectangle(panel.X + 10f * scale, y, panel.Width - 20f * scale, rowHeight);
			Raylib.DrawRectangleRounded(rec, 0.12f, 8, UiTheme.Elevated);
			int fontSize = Math.Max(12, (int)(15f * scale));
			UiTheme.DrawText(UiTheme.Ellipsize(entry.RecentSong.DisplayName, fontSize, (int)(rec.Width - 94f * scale)), (int)(rec.X + 12f * scale), (int)(rec.Y + 7f * scale), fontSize, UiTheme.Text);
			UiTheme.DrawText($"{entry.NoteCount:N0} notes · {PlaybackFormatting.FormatTime(entry.DurationSeconds)}", (int)(rec.X + 12f * scale), (int)(rec.Y + 27f * scale), Math.Max(10, (int)(12f * scale)), UiTheme.Muted);
			if (UiTheme.DrawButton(new Rectangle(rec.X + rec.Width - 70f * scale, rec.Y + 7f * scale, 60f * scale, rec.Height - 14f * scale), "Play", accent))
			{
				result = entry;
			}
			y += rowHeight + rowGap;
		}
		DrawLibraryScrollbar(panel, rows.Count, visibleRows, scrollOffset, scale, rowsTop);
		return result;
	}

	/// <summary>
	/// Draws the "ALL" tab plus one tab per engine that actually has cached songs, and
	/// returns true when the selection changed. Counts are dropped automatically if the
	/// labels would overflow this panel, which is only a third of the window wide.
	/// </summary>
	private static bool DrawEngineTabs(Rectangle panel, OmrEngine[] engines, IReadOnlyList<CachedSongEntry> entries, ref OmrEngine? engineFilter, float scale)
	{
		float tabHeight = Math.Clamp(26f * scale, 22f, 34f);
		int fontSize = Math.Max(14, (int)(18f * Math.Min(1.4f, tabHeight / 44f)));
		float padding = 12f * scale;
		float gap = 6f * scale;
		float usableWidth = panel.Width - 20f * scale;

		string[] plain = new string[engines.Length + 1];
		string[] counted = new string[engines.Length + 1];
		plain[0] = "ALL";
		counted[0] = $"ALL {entries.Count}";
		for (int i = 0; i < engines.Length; i++)
		{
			int count = 0;
			foreach (CachedSongEntry entry in entries)
			{
				if (entry.RecentSong.Engine == engines[i])
				{
					count++;
				}
			}
			plain[i + 1] = GetEngineTabLabel(engines[i]);
			counted[i + 1] = $"{plain[i + 1]} {count}";
		}

		float required = 0f;
		foreach (string label in counted)
		{
			required += UiTheme.MeasureText(label, fontSize) + padding * 2f + gap;
		}
		string[] labels = ((required - gap > usableWidth) ? plain : counted);

		bool changed = false;
		float x = panel.X + 10f * scale;
		float y = panel.Y + 76f * scale;
		for (int i = 0; i < labels.Length; i++)
		{
			float width = UiTheme.MeasureText(labels[i], fontSize) + padding * 2f;
			if (i > 0 && x + width > panel.X + panel.Width - 10f * scale)
			{
				break;
			}
			bool isAll = i == 0;
			bool selected = (isAll ? !engineFilter.HasValue : engineFilter.HasValue && engineFilter.Value == engines[i - 1]);
			Color accent = (isAll ? UiTheme.Lime : GetEngineAccent(engines[i - 1]));
			if (UiTheme.DrawButton(new Rectangle(x, y, width, tabHeight), labels[i], accent, enabled: true, selected) && !selected)
			{
				engineFilter = (isAll ? null : engines[i - 1]);
				changed = true;
			}
			x += width + gap;
		}
		return changed;
	}

	private static string GetEngineTabLabel(OmrEngine engine) => engine switch
	{
		OmrEngine.Homr => "HOMR",
		OmrEngine.Zeus => "ZEUS",
		OmrEngine.MusicXml => "MXML",
		OmrEngine.DirectMidi => "MIDI",
		_ => OmrPipeline.GetEngineName(engine).ToUpperInvariant()
	};

	private static Color GetEngineAccent(OmrEngine engine) => engine switch
	{
		OmrEngine.Zeus => UiTheme.Sky,
		OmrEngine.MusicXml => UiTheme.Warning,
		OmrEngine.DirectMidi => UiTheme.Sky,
		_ => UiTheme.Lime
	};

	/// <summary>
	/// Flattens the engine-ordered cache list into display rows, inserting a section header
	/// row wherever the engine changes. Entries already arrive grouped by engine and sorted
	/// by name, so one pass is enough.
	/// </summary>
	private static List<(OmrEngine Engine, CachedSongEntry? Entry)> BuildCacheRows(IReadOnlyList<CachedSongEntry> entries, bool includeHeaders)
	{
		List<(OmrEngine Engine, CachedSongEntry? Entry)> rows = new();
		OmrEngine? currentEngine = null;
		foreach (CachedSongEntry entry in entries)
		{
			OmrEngine engine = entry.RecentSong.Engine;
			if (includeHeaders && (!currentEngine.HasValue || currentEngine.Value != engine))
			{
				currentEngine = engine;
				rows.Add((engine, null));
			}
			rows.Add((engine, entry));
		}
		return rows;
	}

	/// <summary>
	/// Header and song rows have different heights, so the visible count is measured by
	/// walking forward from the scroll offset until the panel runs out of room.
	/// </summary>
	private static int CountVisibleCacheRows(List<(OmrEngine Engine, CachedSongEntry? Entry)> rows, int scrollOffset, float available, float rowHeight, float rowGap, float headerHeight)
	{
		float used = 0f;
		int count = 0;
		for (int i = Math.Max(0, scrollOffset); i < rows.Count; i++)
		{
			float height = ((rows[i].Entry == null) ? headerHeight : rowHeight);
			if (used + height > available)
			{
				break;
			}
			used += height + rowGap;
			count++;
		}
		return Math.Max(1, count);
	}

	/// <summary>Panel-relative Y of the search box, and of the rows it pushes down.</summary>
	private const float LibrarySearchTop = 40f;
	private const float LibrarySearchHeight = 28f;
	private const float LibraryRowsTop = 78f;
	private const float CacheRowsTop = 112f;

	/// <summary>A plain total, or shown-of-total while a query is narrowing it.</summary>
	private static string FormatLibraryCount(int total, int shown, string noun) =>
		shown == total ? $"{total} {noun}" : $"{shown} of {total}";

	private static IReadOnlyList<TEntry> FilterLibrary<TEntry>(IReadOnlyList<TEntry> entries, string query, Func<TEntry, string> name)
	{
		if (string.IsNullOrWhiteSpace(query))
		{
			return entries;
		}
		List<TEntry> matches = new List<TEntry>();
		foreach (TEntry entry in entries)
		{
			if (LibrarySearchState.Matches(name(entry), query))
			{
				matches.Add(entry);
			}
		}
		return matches;
	}

	/// <summary>
	/// Search box for one library column. Returns true when the query changed, so the
	/// caller can rewind its scroll offset rather than leaving the user parked past the
	/// end of a now-shorter list.
	/// </summary>
	private static bool DrawLibrarySearchBox(Rectangle panel, LibraryColumn column, LibrarySearchState search, float scale)
	{
		Rectangle rec = new Rectangle(panel.X + 10f * scale, panel.Y + LibrarySearchTop * scale, panel.Width - 20f * scale, LibrarySearchHeight * scale);
		bool focused = search.Focused == column;
		if (Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			if (Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), rec))
			{
				search.Focus(column);
				focused = true;
			}
			else if (focused)
			{
				search.ClearFocus();
				focused = false;
			}
		}
		bool changed = false;
		if (focused)
		{
			int character;
			while ((character = Raylib.GetCharPressed()) > 0)
			{
				if (character <= 65535)
				{
					search.Append(column, (char)character);
					changed = true;
				}
			}
			if (Raylib.IsKeyPressed(KeyboardKey.Backspace) && search.Get(column).Length > 0)
			{
				search.Backspace(column);
				changed = true;
			}
			if (Raylib.IsKeyPressed(KeyboardKey.Escape))
			{
				if (search.Get(column).Length > 0)
				{
					search.Set(column, string.Empty);
					changed = true;
				}
				search.ClearFocus();
				focused = false;
			}
			else if (Raylib.IsKeyPressed(KeyboardKey.Enter))
			{
				search.ClearFocus();
				focused = false;
			}
		}
		Raylib.DrawRectangleRounded(rec, 0.24f, 8, UiTheme.Elevated);
		Raylib.DrawRectangleRoundedLinesEx(rec, 0.24f, 8, Math.Max(1f, scale), focused ? UiTheme.Sky : UiTheme.Border);
		string current = search.Get(column);
		int fontSize = Math.Max(11, (int)(13f * scale));
		bool empty = current.Length == 0;
		string text = (empty ? (focused ? "|" : "Search") : (focused ? current + "|" : current));
		UiTheme.DrawText(UiTheme.Ellipsize(text, fontSize, (int)(rec.Width - 40f * scale)), (int)(rec.X + 10f * scale), (int)(rec.Y + (rec.Height - (float)fontSize) / 2f), fontSize, empty ? UiTheme.Muted : UiTheme.Text);
		if (!empty && UiTheme.DrawButton(new Rectangle(rec.X + rec.Width - 26f * scale, rec.Y + 4f * scale, 22f * scale, rec.Height - 8f * scale), "x", UiTheme.Muted))
		{
			search.Set(column, string.Empty);
			search.ClearFocus();
			changed = true;
		}
		return changed;
	}

	private static void DrawLibraryHeader(Rectangle panel, string title, string count, Color accent, float scale)
	{
		UiTheme.DrawCard(panel, scale);
		UiTheme.DrawText(title, (int)(panel.X + 14f * scale), (int)(panel.Y + 14f * scale), Math.Max(13, (int)(16f * scale)), UiTheme.Text);
		int fontSize = Math.Max(10, (int)(12f * scale));
		int countWidth = UiTheme.MeasureText(count, fontSize);
		UiTheme.DrawText(count, (int)(panel.X + panel.Width - (float)countWidth - 16f * scale), (int)(panel.Y + 17f * scale), fontSize, accent);
	}

	private static void DrawLibraryEmpty(Rectangle panel, string message, float scale)
	{
		int fontSize = Math.Max(12, (int)(14f * scale));
		UiTheme.DrawText(UiTheme.Ellipsize(message, fontSize, (int)(panel.Width - 30f * scale)), (int)(panel.X + 15f * scale), (int)(panel.Y + (LibraryRowsTop + 14f) * scale), fontSize, UiTheme.Muted);
	}

	private static int GetVisibleLibraryRows(Rectangle panel, float scale)
	{
		float rowHeight = Math.Clamp(48f * scale, 40f, 58f);
		float rowGap = Math.Clamp(6f * scale, 4f, 9f);
		return Math.Max(1, (int)((panel.Height - (LibraryRowsTop + 8f) * scale) / (rowHeight + rowGap)));
	}

	private static void UpdateLibraryScroll(Rectangle panel, int entryCount, int visibleRows, ref int scrollOffset)
	{
		int max = Math.Max(0, entryCount - visibleRows);
		scrollOffset = Math.Clamp(scrollOffset, 0, max);
		if (Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), panel))
		{
			float mouseWheelMove = Raylib.GetMouseWheelMove();
			if (mouseWheelMove != 0f)
			{
				scrollOffset = Math.Clamp(scrollOffset - Math.Sign(mouseWheelMove), 0, max);
			}
		}
	}

	private static void DrawLibraryScrollbar(Rectangle panel, int entryCount, int visibleRows, int scrollOffset, float scale, float topOffset = LibraryRowsTop)
	{
		if (entryCount > visibleRows)
		{
			float trackHeight = panel.Height - (topOffset + 10f) * scale;
			Rectangle track = new Rectangle(panel.X + panel.Width - 5f * scale, panel.Y + topOffset * scale, 2f * scale, trackHeight);
			Raylib.DrawRectangleRec(track, UiTheme.Border);
			float thumbHeight = Math.Max(20f * scale, trackHeight * (float)visibleRows / (float)entryCount);
			float thumbPosition = (float)scrollOffset / (float)(entryCount - visibleRows);
			Raylib.DrawRectangleRounded(new Rectangle(track.X - scale, track.Y + (trackHeight - thumbHeight) * thumbPosition, 4f * scale, thumbHeight), 0.8f, 6, UiTheme.Muted);
		}
	}

	private static string FormatFileSize(long bytes)
	{
		if (bytes < 0)
		{
			return "Unknown size";
		}
		if (bytes >= 1024)
		{
			double kilobytes = (double)bytes / 1024.0;
			if (kilobytes < 1024.0)
			{
				return $"{kilobytes:0.#} KB";
			}
			return $"{kilobytes / 1024.0:0.#} MB";
		}
		return $"{bytes} B";
	}

	private static bool DrawEngineCard(Rectangle bounds, string title, string description, Color accent, bool selected)
	{
		bool hovered = Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), bounds);
		Raylib.DrawRectangleRounded(bounds, 0.12f, 10, selected ? new Color((int)accent.R, (int)accent.G, (int)accent.B, 38) : (hovered ? UiTheme.Elevated : UiTheme.Surface));
		Raylib.DrawRectangleRoundedLinesEx(bounds, 0.12f, 10, (!selected) ? 1 : 2, selected ? accent : UiTheme.Border);
		int titleSize = Math.Max(17, (int)(21f * Math.Min(1.4f, bounds.Height / 76f)));
		UiTheme.DrawText(title, (int)bounds.X + 16, (int)bounds.Y + 12, titleSize, UiTheme.Text);
		UiTheme.DrawText(description, (int)bounds.X + 16, (int)bounds.Y + 43, Math.Max(12, titleSize - 7), UiTheme.Muted);
		if (selected)
		{
			Raylib.DrawCircle((int)(bounds.X + bounds.Width - 22f), (int)(bounds.Y + 22f), 6f, accent);
		}
		if (hovered)
		{
			return Raylib.IsMouseButtonPressed(MouseButton.Left);
		}
		return false;
	}

	private static void PersistEngine(OmrEngine engine)
	{
		try
		{
			AppSettingsStore.SaveEngine(engine);
		}
		catch (Exception ex)
		{
			Console.Error.WriteLine("[SETTINGS] Selection was not persisted: " + ex.Message);
		}
	}

	private static bool DrawProcessing(UiLayout layout, LoadProgressModel model, bool cancelling)
	{
		float scale = layout.Scale;
		float cardWidth = Math.Min((float)layout.Width - 64f * scale, 720f * scale);
		float cardHeight = 350f * scale;
		Rectangle bounds = new Rectangle(((float)layout.Width - cardWidth) / 2f, ((float)layout.Height - cardHeight) / 2f, cardWidth, cardHeight);
		UiTheme.DrawCard(bounds, scale);
		OmrProgress latest = model.Latest;
		UiTheme.DrawText(cancelling ? "Cancelling conversion" : "Reading sheet music", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 26f * scale), Math.Max(23, (int)(28f * scale)), UiTheme.Text);
		UiTheme.DrawText(UiTheme.Ellipsize(model.FileName, Math.Max(14, (int)(17f * scale)), (int)(bounds.Width - 210f * scale)), (int)(bounds.X + 30f * scale), (int)(bounds.Y + 70f * scale), Math.Max(14, (int)(17f * scale)), UiTheme.Muted);
		Color accent = ((model.Engine == OmrEngine.Zeus) ? UiTheme.Sky : UiTheme.Lime);
		UiTheme.DrawBadge(new Rectangle(bounds.X + bounds.Width - 115f * scale, bounds.Y + 28f * scale, 82f * scale, 28f * scale), OmrPipeline.GetEngineName(model.Engine).ToUpperInvariant(), accent);
		UiTheme.DrawText(UiTheme.Ellipsize(cancelling ? "Stopping Python processes safely…" : (latest?.Message ?? "Starting background worker"), Math.Max(15, (int)(18f * scale)), (int)(bounds.Width - 60f * scale)), (int)(bounds.X + 30f * scale), (int)(bounds.Y + 118f * scale), Math.Max(15, (int)(18f * scale)), UiTheme.Text);
		int? pageCount = latest?.PageCount;
		UiTheme.DrawText((pageCount > 0) ? $"Page {latest.Page ?? Math.Min(latest.CompletedPages.GetValueOrDefault() + 1, latest.PageCount.Value)} of {latest.PageCount}" : FriendlyStage(latest?.Stage), (int)(bounds.X + 30f * scale), (int)(bounds.Y + 155f * scale), Math.Max(13, (int)(16f * scale)), UiTheme.Muted);
		Rectangle bounds2 = new Rectangle(bounds.X + 30f * scale, bounds.Y + 192f * scale, bounds.Width - 60f * scale, 18f * scale);
		bool animated = !cancelling && latest?.Stage == "page_inference" && latest.Status == "started";
		UiTheme.DrawProgressBar(bounds2, model.Fraction, animated, model.ElapsedSeconds);
		UiTheme.DrawText($"{model.Fraction * 100.0:0}%", (int)(bounds2.X + bounds2.Width - 42f * scale), (int)(bounds2.Y + 28f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		string elapsedLabel = "Elapsed  " + PlaybackFormatting.FormatTime(model.ElapsedSeconds);
		// Past recognition the estimate stops meaning anything: these stages are short and
		// not page-paced, so a countdown extrapolated from page rate would be misleading.
		bool isFinishing = latest?.Stage is "normalization" or "midi_write" or "cache_validation";
		string remainingLabel = isFinishing
			? "Finishing…"
			: model.EstimatedRemainingSeconds is double remainingSeconds
				? "Approx. remaining  " + PlaybackFormatting.FormatTime(remainingSeconds)
				: "Estimating…";
		int labelFontSize = Math.Max(13, (int)(15f * scale));
		UiTheme.DrawText(elapsedLabel, (int)(bounds.X + 30f * scale), (int)(bounds.Y + 244f * scale), labelFontSize, UiTheme.Muted);
		int remainingWidth = UiTheme.MeasureText(remainingLabel, labelFontSize);
		UiTheme.DrawText(remainingLabel, (int)(bounds.X + bounds.Width - 30f * scale - (float)remainingWidth), (int)(bounds.Y + 244f * scale), labelFontSize, UiTheme.Muted);
		return UiTheme.DrawButton(new Rectangle(bounds.X + bounds.Width / 2f - 70f * scale, bounds.Y + bounds.Height - 62f * scale, 140f * scale, 40f * scale), cancelling ? "Cancelling…" : "Cancel  (Esc)", UiTheme.Danger, !cancelling);
	}

	private static string FriendlyStage(string? stage)
	{
		return stage switch
		{
			"cache_lookup" => "Checking cache", 
			"input_inspection" => "Inspecting input", 
			"model_load" => "Loading model", 
			"page_inference" => "Processing pages", 
			"normalization" => "Normalizing score", 
			"midi_write" => "Writing MIDI", 
			"cache_validation" => "Validating cache", 
			"known_failure" => "Known deterministic failure", 
			_ => "Preparing", 
		};
	}

	private static ErrorAction DrawError(UiLayout layout, Exception? exception, LoadRequest? request)
	{
		float scale = layout.Scale;
		float cardWidth = Math.Min((float)layout.Width - 64f * scale, 760f * scale);
		float cardHeight = 390f * scale;
		Rectangle bounds = new Rectangle(((float)layout.Width - cardWidth) / 2f, ((float)layout.Height - cardHeight) / 2f, cardWidth, cardHeight);
		UiTheme.DrawCard(bounds, scale);
		UiTheme.DrawText("Conversion failed", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 26f * scale), Math.Max(24, (int)(30f * scale)), UiTheme.Danger);
		DrawWrappedText(FormatLoadError(exception ?? new InvalidOperationException("Unknown loading error.")), new Rectangle(bounds.X + 30f * scale, bounds.Y + 82f * scale, bounds.Width - 60f * scale, 110f * scale), Math.Max(14, (int)(17f * scale)), UiTheme.Text);
		// One optional hint line, drawn in the same slot either way. The decompiler could
		// not reconstruct this and left it as a goto chain across four labels.
		if (exception is KnownOmrFailureException)
		{
			UiTheme.DrawText("This deterministic result was remembered; the model was not loaded again.", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 205f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Warning);
		}
		else if (exception is OmrPipelineException pipelineFailure &&
			pipelineFailure.ErrorCode is "NORMALIZATION_FAILED" or "MUSICXML_PARSE_FAILED")
		{
			UiTheme.DrawText("The engine could not preserve a reliable score structure. Try the other engine.", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 205f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Warning);
		}

		float y = bounds.Y + bounds.Height - 116f * scale;
		float gap = 10f * scale;
		float buttonWidth = (bounds.Width - 60f * scale - gap * 2f) / 3f;
		if (request?.InputPath != null)
		{
			string label = ((request.Engine == OmrEngine.Zeus) ? "Retry homr" : "Retry Zeus");
			Color accent = ((request.Engine == OmrEngine.Zeus) ? UiTheme.Lime : UiTheme.Sky);
			if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale, y, buttonWidth, 44f * scale), label, accent))
			{
				return ErrorAction.RetryAlternate;
			}
			if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale + buttonWidth + gap, y, buttonWidth, 44f * scale), "Retry anyway", UiTheme.Warning))
			{
				return ErrorAction.RetrySame;
			}
			if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale + (buttonWidth + gap) * 2f, y, buttonWidth, 44f * scale), "Choose file", UiTheme.Sky))
			{
				return ErrorAction.ChooseFile;
			}
		}
		else if (UiTheme.DrawButton(new Rectangle(bounds.X + bounds.Width / 2f - 100f * scale, y, 200f * scale, 44f * scale), "Back to library", UiTheme.Sky))
		{
			return ErrorAction.Back;
		}
		return ErrorAction.None;
	}

	private static void DrawWrappedText(string text, Rectangle bounds, int fontSize, Color color)
	{
		string line = string.Empty;
		float y = bounds.Y;
		foreach (string word in text.Split(' ', StringSplitOptions.RemoveEmptyEntries))
		{
			string candidate = ((line.Length == 0) ? word : (line + " " + word));
			if ((float)UiTheme.MeasureText(candidate, fontSize) > bounds.Width && line.Length > 0)
			{
				UiTheme.DrawText(line, (int)bounds.X, (int)y, fontSize, color);
				y += (float)(fontSize + 7);
				line = word;
				if (y + (float)fontSize > bounds.Y + bounds.Height)
				{
					break;
				}
			}
			else
			{
				line = candidate;
			}
		}
		if (line.Length > 0 && y + (float)fontSize <= bounds.Y + bounds.Height)
		{
			UiTheme.DrawText(line, (int)bounds.X, (int)y, fontSize, color);
		}
	}

	private static void HandleErrorAction(ErrorAction action, LoadRequest? request, ConcurrentQueue<string> selectedFiles, DialogState dialogState, ConcurrentQueue<LoadRequest> loadRequests, ref GameState state)
	{
		switch (action)
		{
		case ErrorAction.RetrySame:
			if (request?.InputPath != null)
			{
				loadRequests.Enqueue(request with
				{
					BypassKnownFailure = true,
					RecentSong = null
				});
			}
			break;
		case ErrorAction.RetryAlternate:
			if (request?.InputPath != null)
			{
				loadRequests.Enqueue(new LoadRequest(request.InputPath, (request.Engine == OmrEngine.Zeus) ? OmrEngine.Homr : OmrEngine.Zeus, BypassKnownFailure: false, null));
			}
			break;
		case ErrorAction.ChooseFile:
			state = GameState.WaitingForFile;
			StartFilePicker(selectedFiles, dialogState);
			break;
		case ErrorAction.Back:
			state = GameState.WaitingForFile;
			break;
		}
	}

	private static void HandlePlaybackKeyboard(PlaybackController playback, PlaybackRateEditor rateEditor, ref GameState state, ref bool sliderDragging, ref bool resumeAfterSlider, ref double sliderPreviewPosition, UiLayout layout)
	{
		if (!rateEditor.IsEditing)
		{
			Rectangle playbackSlider = GetPlaybackSlider(layout);
			Rectangle rec = new Rectangle(playbackSlider.X - 8f, playbackSlider.Y - 16f, playbackSlider.Width + 16f, 42f);
			Vector2 mousePosition = Raylib.GetMousePosition();
			if (!sliderDragging && Raylib.IsMouseButtonPressed(MouseButton.Left) && Raylib.CheckCollisionPointRec(mousePosition, rec))
			{
				sliderDragging = true;
				resumeAfterSlider = playback.IsPlaying;
				sliderPreviewPosition = PlaybackFormatting.PositionFromSlider(mousePosition.X, playbackSlider.X, playbackSlider.Width, playback.Session.TotalDuration);
				playback.Pause();
			}
			else if (sliderDragging && Raylib.IsMouseButtonDown(MouseButton.Left))
			{
				sliderPreviewPosition = PlaybackFormatting.PositionFromSlider(mousePosition.X, playbackSlider.X, playbackSlider.Width, playback.Session.TotalDuration);
			}
			if (sliderDragging && Raylib.IsMouseButtonReleased(MouseButton.Left))
			{
				playback.CommitSilencedSeek(sliderPreviewPosition, resumeAfterSlider);
				sliderDragging = false;
				state = (playback.IsCompleted ? GameState.Completed : GameState.Playing);
			}
			if (!sliderDragging && Raylib.IsKeyPressed(KeyboardKey.Space))
			{
				TogglePlayback(playback, ref state);
			}
			if (!sliderDragging && Raylib.IsKeyPressed(KeyboardKey.Left))
			{
				SeekRelative(playback, -5.0, ref state);
			}
			if (!sliderDragging && Raylib.IsKeyPressed(KeyboardKey.Right))
			{
				SeekRelative(playback, 5.0, ref state);
			}
		}
	}

	private static Rectangle GetPlaybackSlider(UiLayout layout)
	{
		float inset = Math.Clamp(118f * layout.Scale, 90f, 180f);
		return new Rectangle(inset, (float)layout.HeaderHeight - 23f * layout.Scale, (float)layout.Width - inset * 2f, Math.Max(8f, 10f * layout.Scale));
	}

	private static bool DrawPlayback(PlaybackController playback, SongLoadResult song, Keyboard piano, bool sliderDragging, double sliderPreviewPosition, PlaybackRateEditor rateEditor, AudioOffsetEditor offsetEditor, ref GameState state, UiLayout layout)
	{
		float scale = layout.Scale;
		Raylib.DrawRectangle(0, 0, layout.Width, layout.HeaderHeight, UiTheme.Surface);
		if (UiTheme.DrawButton(new Rectangle(18f * scale, 14f * scale, 72f * scale, 34f * scale), "Home", UiTheme.Sky))
		{
			return true;
		}
		UiTheme.DrawText(UiTheme.Ellipsize(song.DisplayName, Math.Max(15, (int)(18f * scale)), (int)((double)layout.Width * 0.38)), (int)(106f * scale), (int)(20f * scale), Math.Max(15, (int)(18f * scale)), UiTheme.Text);
		Color accent = ((song.Engine == OmrEngine.Zeus) ? UiTheme.Sky : UiTheme.Lime);
		// Which output is making the sound. Not decoration: the audio offset below is stored per
		// backend, so without this the control's number is ambiguous - and a silent app should
		// say it is silent rather than leave the user hunting for a broken synthesiser.
		if (activeAudioStatus is AudioOutputStatus audio)
		{
			(string audioLabel, Color audioAccent) = audio switch
			{
				{ IsSilent: true } => ("SILENT", UiTheme.Muted),
				{ Backend: AudioBackend.SoundFont } => ("SYNTH", UiTheme.Lime),
				_ => ("MIDI", UiTheme.Sky)
			};
			// Left of the playback-rate control, which starts at Width - 400. The two badges on
			// the right of the header are already up against it.
			UiTheme.DrawBadge(
				new Rectangle((float)layout.Width - 482f * scale, 14f * scale, 74f * scale, 30f * scale),
				audioLabel,
				audioAccent);
		}
		UiTheme.DrawBadge(new Rectangle((float)layout.Width - 190f * scale, 14f * scale, 74f * scale, 30f * scale), OmrPipeline.GetEngineName(song.Engine).ToUpperInvariant(), accent);
		if (song.LoadedFromCache)
		{
			UiTheme.DrawBadge(new Rectangle((float)layout.Width - 108f * scale, 14f * scale, 88f * scale, 30f * scale), "CACHE", UiTheme.Muted);
		}
		UiTheme.DrawText($"{song.NoteCount:N0} notes", (int)(106f * scale), (int)(46f * scale), Math.Max(11, (int)(13f * scale)), UiTheme.Muted);
		float transportLeft = (float)layout.Width / 2f - 92f * scale;
		if (UiTheme.DrawButton(new Rectangle(transportLeft, 10f * scale, 52f * scale, 38f * scale), "−5", UiTheme.Sky))
		{
			SeekRelative(playback, -5.0, ref state);
		}
		if (UiTheme.DrawButton(new Rectangle(transportLeft + 62f * scale, 7f * scale, 60f * scale, 44f * scale), playback.IsPlaying ? "Pause" : "Play", UiTheme.Sky))
		{
			TogglePlayback(playback, ref state);
		}
		if (UiTheme.DrawButton(new Rectangle(transportLeft + 132f * scale, 10f * scale, 52f * scale, 38f * scale), "+5", UiTheme.Sky))
		{
			SeekRelative(playback, 5.0, ref state);
		}
		DrawPlaybackRateControl(playback, rateEditor, layout);
		Rectangle playbackSlider = GetPlaybackSlider(layout);
		// Dragging previews a position the clock has not moved to yet, so everything below
		// follows the preview rather than the controller until the drag is committed.
		double position = (sliderDragging ? sliderPreviewPosition : playback.Position);
		double progress = ((playback.Session.TotalDuration > 0.0) ? Math.Clamp(position / playback.Session.TotalDuration, 0.0, 1.0) : 0.0);
		UiTheme.DrawProgressBar(playbackSlider, progress, animated: false, 0.0);
		Raylib.DrawCircle((int)(playbackSlider.X + (float)(progress * (double)playbackSlider.Width)), (int)(playbackSlider.Y + playbackSlider.Height / 2f), Math.Max(7f, 8f * scale), UiTheme.Text);
		string timeLabel = PlaybackFormatting.FormatTime(position) + " / " + PlaybackFormatting.FormatTime(playback.Session.TotalDuration);
		int fontSize = Math.Max(12, (int)(14f * scale));
		UiTheme.DrawText(timeLabel, (int)((float)layout.Width / 2f - (float)UiTheme.MeasureText(timeLabel, fontSize) / 2f), (int)(playbackSlider.Y + 15f * scale), fontSize, UiTheme.Muted);
		Vector2 mousePosition = Raylib.GetMousePosition();
		Rectangle sliderHitArea = new Rectangle(playbackSlider.X - 8f, playbackSlider.Y - 16f, playbackSlider.Width + 16f, 42f);
		if (!sliderDragging && Raylib.CheckCollisionPointRec(mousePosition, sliderHitArea))
		{
			UiTheme.DrawText(PlaybackFormatting.FormatTime(PlaybackFormatting.PositionFromSlider(mousePosition.X, playbackSlider.X, playbackSlider.Width, playback.Session.TotalDuration)), Math.Clamp((int)mousePosition.X - 24, (int)playbackSlider.X, (int)(playbackSlider.X + playbackSlider.Width - 48f)), (int)(playbackSlider.Y + 34f * scale), fontSize, UiTheme.Text);
		}
		for (int index = 0; index < piano.Keys.Length; index++)
		{
			piano.Keys[index].IsPressed = !sliderDragging && playback.IsKeyActive(index);
			PianoKey key = piano.Keys[index];
			if (!key.IsBlack)
			{
				Raylib.DrawLine(key.X, layout.HeaderHeight, key.X, layout.HitLineY, new Color((int)UiTheme.Border.R, (int)UiTheme.Border.G, (int)UiTheme.Border.B, 72));
			}
		}
		double lookAhead = Math.Max(1.0, (double)(layout.HitLineY - layout.HeaderHeight) / layout.FallSpeed + 1.0);
		(int Start, int End) visibleRange = playback.Session.GetVisibleRange(position, 1.0, lookAhead);
		for (int index = visibleRange.Start; index < visibleRange.End; index++)
		{
			Note note = playback.Session.Notes[index];
			PianoKey key = piano.Keys[note.TargetKeyIndex];
			int bottomY = layout.HitLineY - (int)Math.Floor((note.StartTime - position) * layout.FallSpeed);
			int noteHeight = Math.Max(1, (int)(note.Duration * layout.FallSpeed));
			int topY = bottomY - noteHeight;
			if (topY <= layout.Height && bottomY >= layout.HeaderHeight)
			{
				DrawFallingNote(note, key, topY, bottomY, scale);
			}
		}
		piano.Draw();
		if (sliderDragging)
		{
			UiTheme.DrawText("SEEK PREVIEW", layout.Width / 2 - 68, layout.HeaderHeight + 12, Math.Max(14, (int)(17f * scale)), UiTheme.Warning);
		}
		else if (!playback.IsPlaying)
		{
			string statusLabel = ((state == GameState.Completed) ? "COMPLETED" : "PAUSED");
			int statusFontSize = Math.Max(24, (int)(34f * scale));
			UiTheme.DrawText(statusLabel, layout.Width / 2 - UiTheme.MeasureText(statusLabel, statusFontSize) / 2, layout.HeaderHeight + 18, statusFontSize, UiTheme.Warning);
		}
		DrawAudioOffsetControl(playback, offsetEditor, layout);
		return false;
	}

	/// <summary>
	/// Audio-offset stepper with a typed field, built like DrawPlaybackRateControl so
	/// the two read as the same control. Typing matters here: a 5ms nudge is below the
	/// roughly 20-40ms at which a listener notices an audio-visual shift, so finding the
	/// right value by stepping alone means dozens of presses that each feel like nothing.
	/// </summary>
	private static void DrawAudioOffsetControl(PlaybackController playback, AudioOffsetEditor editor, UiLayout layout)
	{
		float scale = layout.Scale;
		float buttonSize = 26f * scale;
		float width = 64f * scale;
		float height = 26f * scale;
		float x = (float)layout.Width - 16f * scale - (2f * buttonSize + width + 10f * scale);
		float y = (float)layout.HitLineY - height - 12f * scale;
		int current = (int)Math.Round(playback.AudioOffsetSeconds * 1000.0);
		int labelSize = Math.Max(10, (int)(12f * scale));
		UiTheme.DrawText("AUDIO OFFSET", (int)(x - (float)UiTheme.MeasureText("AUDIO OFFSET", labelSize) - 10f * scale), (int)(y + (height - (float)labelSize) / 2f), labelSize, UiTheme.Muted);
		if (UiTheme.DrawButton(new Rectangle(x, y, buttonSize, height), "−", UiTheme.Muted, !editor.IsEditing && current > AppSettingsStore.MinimumAudioOffsetMilliseconds))
		{
			editor.Cancel();
			StepAudioOffset(playback, -AudioOffsetRules.StepMilliseconds);
		}
		Rectangle valueBox = new Rectangle(x + buttonSize + 5f * scale, y, width, height);
		Raylib.DrawRectangleRounded(valueBox, 0.16f, 8, UiTheme.Elevated);
		Color borderColor = ((editor.Error != null) ? UiTheme.Danger : (editor.IsEditing ? UiTheme.Sky : UiTheme.Border));
		Raylib.DrawRectangleRoundedLinesEx(valueBox, 0.16f, 8, Math.Max(1f, scale), borderColor);
		if (Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			int typedOffset;
			if (Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), valueBox))
			{
				if (!editor.IsEditing)
				{
					editor.Begin(current);
				}
			}
			else if (editor.IsEditing && editor.TryCommit(out typedOffset))
			{
				ApplyAudioOffset(playback, typedOffset);
			}
		}
		if (editor.IsEditing)
		{
			int charPressed;
			while ((charPressed = Raylib.GetCharPressed()) > 0)
			{
				if (charPressed <= 65535)
				{
					editor.Append((char)charPressed);
				}
			}
			if (Raylib.IsKeyPressed(KeyboardKey.Backspace))
			{
				editor.Backspace();
			}
			if (Raylib.IsKeyPressed(KeyboardKey.Enter) && editor.TryCommit(out var typedOffset))
			{
				ApplyAudioOffset(playback, typedOffset);
			}
			else if (Raylib.IsKeyPressed(KeyboardKey.Escape))
			{
				editor.Cancel();
			}
		}
		string valueText = (editor.IsEditing ? (editor.Text + "|") : $"{current} ms");
		int valueFontSize = Math.Max(11, (int)(13f * scale));
		UiTheme.DrawText(valueText, (int)(valueBox.X + (valueBox.Width - (float)UiTheme.MeasureText(valueText, valueFontSize)) / 2f), (int)(valueBox.Y + (valueBox.Height - (float)valueFontSize) / 2f), valueFontSize, UiTheme.Text);
		if (UiTheme.DrawButton(new Rectangle(valueBox.X + valueBox.Width + 5f * scale, y, buttonSize, height), "+", UiTheme.Muted, !editor.IsEditing && current < AppSettingsStore.MaximumAudioOffsetMilliseconds))
		{
			editor.Cancel();
			StepAudioOffset(playback, AudioOffsetRules.StepMilliseconds);
		}
		if (editor.Error != null)
		{
			UiTheme.DrawText(editor.Error, (int)valueBox.X, (int)(valueBox.Y + valueBox.Height + 2f * scale), Math.Max(9, (int)(11f * scale)), UiTheme.Danger);
		}
	}

	private static void StepAudioOffset(PlaybackController playback, int deltaMilliseconds)
	{
		int current = (int)Math.Round(playback.AudioOffsetSeconds * 1000.0);
		ApplyAudioOffset(playback, AppSettingsStore.Clamp(current + deltaMilliseconds));
	}

	/// <summary>
	/// Which output is making sound this run. Held here rather than passed down because the
	/// offset control is reached through several layers of drawing code, and there is exactly
	/// one audio output per process.
	/// </summary>
	private static AudioBackend activeAudioBackend = AudioBackend.MidiDevice;

	/// <summary>
	/// What the audio badge shows, as plain data rather than a live query, so the headless
	/// smoke render can fabricate any state - including the degraded ones - on a machine with
	/// no audio device and no soundfont.
	/// </summary>
	private static AudioOutputStatus? activeAudioStatus;

	/// <summary>
	/// The stored backend choice, which can differ from <see cref="activeAudioBackend"/> until
	/// the next launch - either because the user just switched, or because the preferred backend
	/// could not be opened and <see cref="AudioOutput.Create"/> fell back.
	/// </summary>
	private static AudioBackend selectedAudioBackend = AudioBackend.SoundFont;

	private static void PersistAudioBackend(AudioBackend backend)
	{
		selectedAudioBackend = backend;
		try
		{
			AppSettingsStore.SaveAudioBackend(backend);
		}
		catch (Exception error)
		{
			Console.Error.WriteLine("[SETTINGS] Could not save the audio backend: " + error.Message);
		}
	}

	/// <summary>Applies the offset and persists it, so calibration survives a restart.</summary>
	/// <remarks>
	/// Saved against the backend it was measured on. The two are not interchangeable: the stored
	/// MIDI-device value is the user's own by-ear calibration against VirtualMIDISynth, and the
	/// built-in synth's latency is a fraction of it, so writing one over the other would either
	/// mis-time the synth or destroy a measurement that cannot be recovered.
	/// </remarks>
	private static void ApplyAudioOffset(PlaybackController playback, int milliseconds)
	{
		int updated = AppSettingsStore.Clamp(milliseconds);
		if (updated != (int)Math.Round(playback.AudioOffsetSeconds * 1000.0))
		{
			playback.SetAudioOffsetSeconds((double)updated / 1000.0);
			if (activeAudioBackend == AudioBackend.SoundFont)
			{
				AppSettingsStore.SaveSynthAudioOffsetMilliseconds(updated);
			}
			else
			{
				AppSettingsStore.SaveAudioOffsetMilliseconds(updated);
			}
		}
	}

	private static void DrawPlaybackRateControl(PlaybackController playback, PlaybackRateEditor editor, UiLayout layout)
	{
		float scale = layout.Scale;
		float controlLeft = (float)layout.Width - 400f * scale;
		float y = 12f * scale;
		float buttonSize = 32f * scale;
		float width = 72f * scale;
		float height = 34f * scale;
		bool canDecrease = playback.PlaybackRate > 0.050000001;
		bool canIncrease = playback.PlaybackRate < 1.999999999;
		if (UiTheme.DrawButton(new Rectangle(controlLeft, y, buttonSize, height), "−", UiTheme.Muted, canDecrease))
		{
			editor.Cancel();
			StepPlaybackRate(playback, -1);
		}
		Rectangle valueBox = new Rectangle(controlLeft + buttonSize + 5f * scale, y, width, height);
		Raylib.DrawRectangleRounded(valueBox, 0.16f, 8, UiTheme.Elevated);
		Color borderColor = ((editor.Error != null) ? UiTheme.Danger : (editor.IsEditing ? UiTheme.Sky : UiTheme.Border));
		Raylib.DrawRectangleRoundedLinesEx(valueBox, 0.16f, 8, Math.Max(1f, scale), borderColor);
		if (Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			double typedRate;
			if (Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), valueBox))
			{
				if (!editor.IsEditing)
				{
					editor.Begin(playback.PlaybackRate);
				}
			}
			else if (editor.IsEditing && editor.TryCommit(out typedRate))
			{
				playback.SetPlaybackRate(typedRate);
			}
		}
		if (editor.IsEditing)
		{
			int charPressed;
			while ((charPressed = Raylib.GetCharPressed()) > 0)
			{
				if (charPressed <= 65535)
				{
					editor.Append((char)charPressed);
				}
			}
			if (Raylib.IsKeyPressed(KeyboardKey.Backspace))
			{
				editor.Backspace();
			}
			if (Raylib.IsKeyPressed(KeyboardKey.Enter) && editor.TryCommit(out var typedRate))
			{
				playback.SetPlaybackRate(typedRate);
			}
			else if (Raylib.IsKeyPressed(KeyboardKey.Escape))
			{
				editor.Cancel();
			}
		}
		string valueText = (editor.IsEditing ? (editor.Text + "|") : $"{playback.PlaybackRate:0.00}x");
		int valueFontSize = Math.Max(11, (int)(14f * scale));
		UiTheme.DrawText(valueText, (int)(valueBox.X + (valueBox.Width - (float)UiTheme.MeasureText(valueText, valueFontSize)) / 2f), (int)(valueBox.Y + (valueBox.Height - (float)valueFontSize) / 2f), valueFontSize, UiTheme.Text);
		if (UiTheme.DrawButton(new Rectangle(valueBox.X + valueBox.Width + 5f * scale, y, buttonSize, height), "+", UiTheme.Muted, canIncrease))
		{
			editor.Cancel();
			StepPlaybackRate(playback, 1);
		}
		if (editor.Error != null)
		{
			UiTheme.DrawText(editor.Error, (int)valueBox.X, (int)(valueBox.Y + valueBox.Height + 2f * scale), Math.Max(9, (int)(11f * scale)), UiTheme.Danger);
		}
	}

	private static void StepPlaybackRate(PlaybackController playback, int direction)
	{
		playback.SetPlaybackRate(PlaybackRateRules.Step(playback.PlaybackRate, direction));
	}

	private static void DrawFallingNote(Note note, PianoKey key, int rawTopY, int rawBottomY, float scale)
	{
		float topInset = Math.Clamp(3f * scale, 2f, 5f);
		// The bottom edge is the note's actual moment, so it is not inset: insetting it
		// held every note a pixel or two short of the hit line, which reads as the whole
		// field sitting high. Only the top is pulled in, to leave a gap between notes.
		float bottomEdge = (float)rawBottomY;
		float height = Math.Max(7f * scale, bottomEdge - ((float)rawTopY + topInset));
		// Short notes grow upward from the hit line rather than downward past it, so a
		// clamped note still lands at the right time.
		float topEdge = bottomEdge - height;
		float noteWidth = Math.Max(20f * scale, (float)key.Width - 2f * scale);
		float x = (float)key.X + (float)key.Width / 2f - noteWidth / 2f;
		Rectangle bounds = new Rectangle(x, topEdge, noteWidth, height);
		Raylib.DrawRectangleRounded(bounds, 0.24f, 8, note.Color);
		Raylib.DrawRectangleRoundedLinesEx(
			bounds,
			0.24f,
			8,
			Math.Max(1f, 1.5f * scale),
			new Color(Math.Max(0, note.Color.R - 55), Math.Max(0, note.Color.G - 55), Math.Max(0, note.Color.B - 55), 255));
		string pitchClass = note.PitchClass;
		int labelSize = Math.Clamp((int)(13f * scale), 9, 16);
		while (labelSize > 8 && (float)UiTheme.MeasureText(pitchClass, labelSize) > bounds.Width - 3f * scale)
		{
			labelSize--;
		}
		int labelWidth = UiTheme.MeasureText(pitchClass, labelSize);
		int labelX = (int)(bounds.X + (bounds.Width - (float)labelWidth) / 2f);
		int labelY = (int)(bounds.Y + (bounds.Height - (float)labelSize) / 2f);
		UiTheme.DrawText(pitchClass, labelX + 1, labelY + 1, labelSize, new Color(0, 0, 0, 210));
		UiTheme.DrawText(pitchClass, labelX, labelY, labelSize, UiTheme.Text);
	}

	private static void TogglePlayback(PlaybackController playback, ref GameState state)
	{
		if (playback.IsPlaying)
		{
			playback.Pause();
			return;
		}
		playback.Resume();
		state = GameState.Playing;
	}

	private static void SeekRelative(PlaybackController playback, double seconds, ref GameState state)
	{
		bool isPlaying = playback.IsPlaying;
		playback.Seek(playback.Position + seconds, isPlaying);
		state = (playback.IsCompleted ? GameState.Completed : GameState.Playing);
	}

	private static string FormatLoadError(Exception exception)
	{
		if (exception is OmrPipelineException ex && !string.IsNullOrWhiteSpace(ex.ErrorCode))
		{
			string pageSuffix = ((!ex.Page.HasValue) ? string.Empty : $" on page {ex.Page}");
			// These two codes get a plain-language message; every other code is shown raw,
			// because the code and stage are what make an unfamiliar failure searchable.
			if (ex.ErrorCode is "NORMALIZATION_FAILED" or "MUSICXML_PARSE_FAILED")
			{
				return "The engine produced an unreliable MusicXML structure" + pageSuffix + ": " + ex.Message;
			}
			return $"{ex.ErrorCode} ({ex.Stage ?? "unknown stage"}){pageSuffix}: {ex.Message}";
		}
		if (exception.Message.Length > 240)
		{
			return exception.Message.Substring(0, 240) + "...";
		}
		return exception.Message;
	}
}
