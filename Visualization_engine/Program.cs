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
		DrawStartupNotice("Connecting to audio device...");
		using OutputDevice outputDevice = TryOpenSynthDevice(out string audioWarning);
		IMidiOutput midiOutput;
		if ((object)outputDevice == null)
		{
			midiOutput = new NullMidiOutput();
		}
		else
		{
			outputDevice.PrepareForEventsSending();
			midiOutput = new DryWetMidiOutput(outputDevice);
		}
		midiOutput.AllNotesOff();
		UiLayout layout = UiLayout.Create(Raylib.GetScreenWidth(), Raylib.GetScreenHeight());
		Keyboard keyboard = new Keyboard(layout.Width, layout.HitLineY, layout.KeyboardHeight);
		int num = layout.Width;
		int num2 = layout.Height;
		ConcurrentQueue<string> concurrentQueue = new ConcurrentQueue<string>();
		ConcurrentQueue<LoadRequest> concurrentQueue2 = new ConcurrentQueue<LoadRequest>();
		LoadResultHandoff<SongLoadResult> loadResults = new LoadResultHandoff<SongLoadResult>();
		LoadProgressTracker progressQueue = new LoadProgressTracker();
		LoadProgressModel loadProgressModel = new LoadProgressModel();
		using CancellationTokenSource cancellationTokenSource2 = new CancellationTokenSource();
		CancellationTokenSource cancellationTokenSource = null;
		Task task = null;
		DialogState dialogState = new DialogState();
		GameState state = GameState.WaitingForFile;
		OmrEngine selectedEngine = AppSettingsStore.LoadEngine();
		LoadRequest request2 = null;
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
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.F11))
			{
				Raylib.ToggleFullscreen();
			}
			int screenWidth = Raylib.GetScreenWidth();
			int screenHeight = Raylib.GetScreenHeight();
			if (screenWidth != num || screenHeight != num2)
			{
				layout = UiLayout.Create(screenWidth, screenHeight);
				keyboard.Resize(layout.Width, layout.HitLineY, layout.KeyboardHeight);
				num = screenWidth;
				num2 = screenHeight;
			}
			OmrProgress progress;
			while (progressQueue.TryTake(out progress) && (object)progress != null)
			{
				loadProgressModel.Apply(progress);
			}
			if (loadResults.TryTake(out LoadCompletion<SongLoadResult> completion) && (object)completion != null)
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
					if ((object)value != null)
					{
						List<Note> notes = value.Notes;
						if (notes != null && notes.Count > 0)
						{
							playbackController?.Stop();
							songLoadResult = value;
							playbackController = new PlaybackController(
								new PlaybackSession(
									value.Notes,
									(double)AppSettingsStore.LoadAudioOffsetMilliseconds() / 1000.0),
								midiOutput);
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
			HandleDroppedFiles(state, concurrentQueue);
			string result;
			while (state == GameState.WaitingForFile && concurrentQueue.TryDequeue(out result))
			{
				concurrentQueue2.Enqueue(new LoadRequest(result, selectedEngine, BypassKnownFailure: false, null));
			}
			bool flag = ((state == GameState.WaitingForFile || state == GameState.Error) ? true : false);
			if (flag && concurrentQueue2.TryDequeue(out var request))
			{
				request2 = request;
				exception = null;
				message = null;
				if (NeedsReuseConfirmation(request))
				{
					state = GameState.ConfirmReuse;
				}
				else
				{
					loadProgressModel.Start(request.DisplayName, request.Engine);
					cancellationTokenSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationTokenSource2.Token);
					CancellationToken token = cancellationTokenSource.Token;
					state = GameState.Processing;
					task = Task.Run(delegate
					{
						LoadSong(request, loadResults, progressQueue, token);
					});
				}
			}
			flag = playbackController != null;
			if (flag)
			{
				bool flag2 = state == GameState.Playing || state == GameState.Completed;
				flag = flag2;
			}
			if (flag)
			{
				HandlePlaybackKeyboard(playbackController, playbackRateEditor, ref state, ref sliderDragging, ref resumeAfterSlider, ref sliderPreviewPosition, layout);
				if (!playbackRateEditor.IsEditing && !audioOffsetEditor.IsEditing && !sliderDragging)
				{
					int num7 = 0;
					if ((bool)Raylib.IsKeyPressed(KeyboardKey.LeftBracket))
					{
						num7 = -AudioOffsetRules.StepMilliseconds;
					}
					else if ((bool)Raylib.IsKeyPressed(KeyboardKey.RightBracket))
					{
						num7 = AudioOffsetRules.StepMilliseconds;
					}
					if (num7 != 0)
					{
						StepAudioOffset(playbackController, num7);
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
				if (browseRequested || (!librarySearch.IsTyping && (bool)Raylib.IsKeyPressed(KeyboardKey.B)))
				{
					StartFilePicker(concurrentQueue, dialogState);
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
				if ((object)loadRequest != null)
				{
					concurrentQueue2.Enqueue(loadRequest);
				}
				break;
			}
			case GameState.ConfirmReuse:
			{
				ReuseAction reuseAction = DrawConfirmReuse(layout, request2);
				if ((bool)Raylib.IsKeyPressed(KeyboardKey.Escape))
				{
					reuseAction = ReuseAction.Cancel;
				}
				HandleReuseAction(reuseAction, request2, concurrentQueue2, ref state);
				break;
			}
			case GameState.Processing:
				if (DrawProcessing(layout, loadProgressModel, cancelling: false) || (bool)Raylib.IsKeyPressed(KeyboardKey.Escape))
				{
					cancellationTokenSource?.Cancel();
					state = GameState.Cancelling;
				}
				break;
			case GameState.Cancelling:
				DrawProcessing(layout, loadProgressModel, cancelling: true);
				break;
			case GameState.Error:
				HandleErrorAction(DrawError(layout, exception, request2), request2, concurrentQueue, dialogState, concurrentQueue2, ref state);
				break;
			case GameState.Playing:
			case GameState.Completed:
				if (playbackController != null && (object)songLoadResult != null && DrawPlayback(playbackController, songLoadResult, keyboard, sliderDragging, sliderPreviewPosition, playbackRateEditor, audioOffsetEditor, ref state, layout))
				{
					playbackController.Stop();
					playbackRateEditor.Cancel();
					state = GameState.WaitingForFile;
				}
				break;
			}
			Raylib.EndDrawing();
		}
		cancellationTokenSource2.Cancel();
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
	/// Opens a MIDI synthesiser, preferring VirtualMIDISynth and falling back to any
	/// available device. Returns null when the machine has no MIDI output at all; the
	/// caller then runs silently rather than failing to start.
	/// </summary>
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

	private static OutputDevice TryOpenSynthDevice(out string warning)
	{
		warning = null;
		try
		{
			OutputDevice byName = OutputDevice.GetByName("VirtualMIDISynth #1");
			Console.WriteLine("[AUDIO SYSTEM] Connected to VirtualMIDISynth.");
			return byName;
		}
		catch (Exception ex)
		{
			OutputDevice outputDevice;
			try
			{
				outputDevice = OutputDevice.GetAll().FirstOrDefault();
			}
			catch (Exception discovery)
			{
				Console.Error.WriteLine("[AUDIO SYSTEM] Could not enumerate MIDI devices. " + discovery.Message);
				outputDevice = null;
			}
			if ((object)outputDevice == null)
			{
				warning = "No MIDI output device found. Playback is silent; install a MIDI synthesizer such as VirtualMIDISynth for sound.";
				Console.Error.WriteLine("[AUDIO SYSTEM] " + warning + " " + ex.Message);
				return null;
			}
			Console.Error.WriteLine("[AUDIO SYSTEM] VirtualMIDISynth unavailable; using " + outputDevice.Name + ". " + ex.Message);
			return outputDevice;
		}
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
			SongLoadResult value = (((object)request.RecentSong != null) ? SongCache.LoadRecent(request.RecentSong) : SongCache.LoadOrCreateDetailed(request.InputPath ?? throw new InvalidOperationException("Load request has no source path."), request.Engine, cancellationToken, progress, request.BypassKnownFailure, request.ForceReprocess));
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
		if (request.ReuseConfirmed || request.ForceReprocess || (object)request.RecentSong != null)
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
		if ((object)request == null)
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
			if ((object)request != null)
			{
				loadRequests.Enqueue(request with { ReuseConfirmed = true });
			}
			state = GameState.WaitingForFile;
			break;
		case ReuseAction.Reprocess:
			if ((object)request != null)
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
		float num = Math.Min((float)layout.Width - 48f * scale, 1120f * scale);
		float num2 = ((float)layout.Width - num) / 2f;
		Rectangle bounds = new Rectangle(num2, 88f * scale, num, 74f * scale);
		UiTheme.DrawCard(bounds, scale);
		UiTheme.DrawText("Drop a PDF or score image here", (int)(bounds.X + 24f * scale), (int)(bounds.Y + 14f * scale), Math.Max(16, (int)(20f * scale)), UiTheme.Text);
		UiTheme.DrawText("PDF, PNG, JPEG, TIFF, BMP or WebP", (int)(bounds.X + 24f * scale), (int)(bounds.Y + 43f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		Rectangle bounds2 = new Rectangle(bounds.X + bounds.Width - 150f * scale, bounds.Y + 16f * scale, 122f * scale, 42f * scale);
		browseRequested = UiTheme.DrawButton(bounds2, "Browse", UiTheme.Sky);
		Rectangle bounds3 = new Rectangle(bounds2.X - 112f * scale, bounds2.Y, 98f * scale, bounds2.Height);
		refreshRequested = UiTheme.DrawButton(bounds3, "Refresh", UiTheme.Muted);
		UiTheme.DrawText("OMR ENGINE", (int)num2, (int)(174f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		float num3 = 16f * scale;
		float num4 = (num - num3) / 2f;
		Rectangle bounds4 = new Rectangle(num2, 194f * scale, num4, 64f * scale);
		Rectangle bounds5 = new Rectangle(num2 + num4 + num3, 194f * scale, num4, 64f * scale);
		if (DrawEngineCard(bounds4, "Zeus GPU", "Experimental rhythm · CUDA-only", UiTheme.Sky, selectedEngine == OmrEngine.Zeus))
		{
			selectedEngine = OmrEngine.Zeus;
			PersistEngine(selectedEngine);
		}
		if (DrawEngineCard(bounds5, "homr", "Faster · general sheet music", UiTheme.Lime, selectedEngine == OmrEngine.Homr))
		{
			selectedEngine = OmrEngine.Homr;
			PersistEngine(selectedEngine);
		}
		// Gated on focus: these would otherwise fire on the o and h in a typed query.
		if (!librarySearch.IsTyping && (bool)Raylib.IsKeyPressed(KeyboardKey.O))
		{
			selectedEngine = OmrEngine.Zeus;
			PersistEngine(selectedEngine);
		}
		else if (!librarySearch.IsTyping && (bool)Raylib.IsKeyPressed(KeyboardKey.H))
		{
			selectedEngine = OmrEngine.Homr;
			PersistEngine(selectedEngine);
		}
		float num5 = 274f * scale;
		float num6 = 14f * scale;
		float num7 = (num - 2 * num6) / 3f;
		float height = Math.Max(170f * scale, (float)layout.Height - num5 - 24f * scale);
		Rectangle panel = new Rectangle(num2, num5, num7, height);
		Rectangle panel2 = new Rectangle(num2 + num7 + num6, num5, num7, height);
		Rectangle panel3 = new Rectangle(num2 + 2 * (num7 + num6), num5, num7, height);
		PdfLibraryEntry pdfLibraryEntry = DrawPdfLibraryPanel(panel, pdfLibrary, ref pdfScrollOffset, librarySearch, scale);
		CachedSongEntry cachedSongEntry = DrawCacheLibraryPanel(panel2, cachedSongs, ref cacheScrollOffset, ref cacheEngineFilter, librarySearch, scale);
		MidiLibraryEntry midiLibraryEntry = DrawMidiLibraryPanel(panel3, midiLibrary, ref midiScrollOffset, librarySearch, scale);
		if (!string.IsNullOrWhiteSpace(message))
		{
			Rectangle rec = new Rectangle(num2 + 8f * scale, (float)layout.Height - 47f * scale, num - 16f * scale, 32f * scale);
			Raylib.DrawRectangleRounded(rec, 0.18f, 8, UiTheme.Elevated);
			UiTheme.DrawText(UiTheme.Ellipsize(message, 13, (int)(rec.Width - 20f * scale)), (int)(rec.X + 10f * scale), (int)(rec.Y + 8f * scale), 13, UiTheme.Warning);
		}
		if ((object)pdfLibraryEntry != null)
		{
			return new LoadRequest(pdfLibraryEntry.FullPath, selectedEngine, BypassKnownFailure: false, null);
		}
		if ((object)cachedSongEntry != null)
		{
			return new LoadRequest(null, cachedSongEntry.RecentSong.Engine, BypassKnownFailure: false, cachedSongEntry.RecentSong);
		}
		if ((object)midiLibraryEntry != null)
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
		float num = Math.Clamp(48f * scale, 40f, 58f);
		float num2 = Math.Clamp(6f * scale, 4f, 9f);
		float num3 = panel.Y + LibraryRowsTop * scale;
		for (int i = 0; i < visibleLibraryRows && scrollOffset + i < entries.Count; i++)
		{
			PdfLibraryEntry pdfLibraryEntry = entries[scrollOffset + i];
			Rectangle rec = new Rectangle(panel.X + 10f * scale, num3 + (float)i * (num + num2), panel.Width - 20f * scale, num);
			Raylib.DrawRectangleRounded(rec, 0.12f, 8, UiTheme.Elevated);
			int fontSize = Math.Max(12, (int)(15f * scale));
			UiTheme.DrawText(UiTheme.Ellipsize(pdfLibraryEntry.DisplayName, fontSize, (int)(rec.Width - 94f * scale)), (int)(rec.X + 12f * scale), (int)(rec.Y + 7f * scale), fontSize, UiTheme.Text);
			UiTheme.DrawText(FormatFileSize(pdfLibraryEntry.SizeBytes), (int)(rec.X + 12f * scale), (int)(rec.Y + 27f * scale), Math.Max(10, (int)(12f * scale)), UiTheme.Muted);
			if (UiTheme.DrawButton(new Rectangle(rec.X + rec.Width - 72f * scale, rec.Y + 7f * scale, 62f * scale, rec.Height - 14f * scale), "Load", UiTheme.Sky))
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
		float num = Math.Clamp(48f * scale, 40f, 58f);
		float num2 = Math.Clamp(6f * scale, 4f, 9f);
		float num3 = panel.Y + LibraryRowsTop * scale;
		for (int i = 0; i < visibleLibraryRows && scrollOffset + i < entries.Count; i++)
		{
			MidiLibraryEntry entry = entries[scrollOffset + i];
			Rectangle rec = new Rectangle(panel.X + 10f * scale, num3 + (float)i * (num + num2), panel.Width - 20f * scale, num);
			Raylib.DrawRectangleRounded(rec, 0.12f, 8, UiTheme.Elevated);
			int fontSize = Math.Max(12, (int)(15f * scale));
			UiTheme.DrawText(UiTheme.Ellipsize(entry.DisplayName, fontSize, (int)(rec.Width - 94f * scale)), (int)(rec.X + 12f * scale), (int)(rec.Y + 7f * scale), fontSize, UiTheme.Text);
			UiTheme.DrawText(FormatFileSize(entry.SizeBytes), (int)(rec.X + 12f * scale), (int)(rec.Y + 27f * scale), Math.Max(10, (int)(12f * scale)), UiTheme.Muted);
			if (UiTheme.DrawButton(new Rectangle(rec.X + rec.Width - 72f * scale, rec.Y + 7f * scale, 62f * scale, rec.Height - 14f * scale), "Play", UiTheme.Sky))
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
		if ((bool)Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			if ((bool)Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), rec))
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
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.Backspace) && search.Get(column).Length > 0)
			{
				search.Backspace(column);
				changed = true;
			}
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.Escape))
			{
				if (search.Get(column).Length > 0)
				{
					search.Set(column, string.Empty);
					changed = true;
				}
				search.ClearFocus();
				focused = false;
			}
			else if ((bool)Raylib.IsKeyPressed(KeyboardKey.Enter))
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
		int num = UiTheme.MeasureText(count, fontSize);
		UiTheme.DrawText(count, (int)(panel.X + panel.Width - (float)num - 16f * scale), (int)(panel.Y + 17f * scale), fontSize, accent);
	}

	private static void DrawLibraryEmpty(Rectangle panel, string message, float scale)
	{
		int fontSize = Math.Max(12, (int)(14f * scale));
		UiTheme.DrawText(UiTheme.Ellipsize(message, fontSize, (int)(panel.Width - 30f * scale)), (int)(panel.X + 15f * scale), (int)(panel.Y + (LibraryRowsTop + 14f) * scale), fontSize, UiTheme.Muted);
	}

	private static int GetVisibleLibraryRows(Rectangle panel, float scale)
	{
		float num = Math.Clamp(48f * scale, 40f, 58f);
		float num2 = Math.Clamp(6f * scale, 4f, 9f);
		return Math.Max(1, (int)((panel.Height - (LibraryRowsTop + 8f) * scale) / (num + num2)));
	}

	private static void UpdateLibraryScroll(Rectangle panel, int entryCount, int visibleRows, ref int scrollOffset)
	{
		int max = Math.Max(0, entryCount - visibleRows);
		scrollOffset = Math.Clamp(scrollOffset, 0, max);
		if ((bool)Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), panel))
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
			float num = panel.Height - (topOffset + 10f) * scale;
			Rectangle rec = new Rectangle(panel.X + panel.Width - 5f * scale, panel.Y + topOffset * scale, 2f * scale, num);
			Raylib.DrawRectangleRec(rec, UiTheme.Border);
			float num2 = Math.Max(20f * scale, num * (float)visibleRows / (float)entryCount);
			float num3 = (float)scrollOffset / (float)(entryCount - visibleRows);
			Raylib.DrawRectangleRounded(new Rectangle(rec.X - scale, rec.Y + (num - num2) * num3, 4f * scale, num2), 0.8f, 6, UiTheme.Muted);
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
			double num = (double)bytes / 1024.0;
			if (num < 1024.0)
			{
				return $"{num:0.#} KB";
			}
			return $"{num / 1024.0:0.#} MB";
		}
		return $"{bytes} B";
	}

	private static bool DrawEngineCard(Rectangle bounds, string title, string description, Color accent, bool selected)
	{
		bool flag = Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), bounds);
		Raylib.DrawRectangleRounded(bounds, 0.12f, 10, selected ? new Color((int)accent.R, (int)accent.G, (int)accent.B, 38) : (flag ? UiTheme.Elevated : UiTheme.Surface));
		Raylib.DrawRectangleRoundedLinesEx(bounds, 0.12f, 10, (!selected) ? 1 : 2, selected ? accent : UiTheme.Border);
		int num = Math.Max(17, (int)(21f * Math.Min(1.4f, bounds.Height / 76f)));
		UiTheme.DrawText(title, (int)bounds.X + 16, (int)bounds.Y + 12, num, UiTheme.Text);
		UiTheme.DrawText(description, (int)bounds.X + 16, (int)bounds.Y + 43, Math.Max(12, num - 7), UiTheme.Muted);
		if (selected)
		{
			Raylib.DrawCircle((int)(bounds.X + bounds.Width - 22f), (int)(bounds.Y + 22f), 6f, accent);
		}
		if (flag)
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
		float num = Math.Min((float)layout.Width - 64f * scale, 720f * scale);
		float num2 = 350f * scale;
		Rectangle bounds = new Rectangle(((float)layout.Width - num) / 2f, ((float)layout.Height - num2) / 2f, num, num2);
		UiTheme.DrawCard(bounds, scale);
		OmrProgress latest = model.Latest;
		UiTheme.DrawText(cancelling ? "Cancelling conversion" : "Reading sheet music", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 26f * scale), Math.Max(23, (int)(28f * scale)), UiTheme.Text);
		UiTheme.DrawText(UiTheme.Ellipsize(model.FileName, Math.Max(14, (int)(17f * scale)), (int)(bounds.Width - 210f * scale)), (int)(bounds.X + 30f * scale), (int)(bounds.Y + 70f * scale), Math.Max(14, (int)(17f * scale)), UiTheme.Muted);
		Color accent = ((model.Engine == OmrEngine.Zeus) ? UiTheme.Sky : UiTheme.Lime);
		UiTheme.DrawBadge(new Rectangle(bounds.X + bounds.Width - 115f * scale, bounds.Y + 28f * scale, 82f * scale, 28f * scale), OmrPipeline.GetEngineName(model.Engine).ToUpperInvariant(), accent);
		UiTheme.DrawText(UiTheme.Ellipsize(cancelling ? "Stopping Python processes safely…" : (latest?.Message ?? "Starting background worker"), Math.Max(15, (int)(18f * scale)), (int)(bounds.Width - 60f * scale)), (int)(bounds.X + 30f * scale), (int)(bounds.Y + 118f * scale), Math.Max(15, (int)(18f * scale)), UiTheme.Text);
		int? num3 = latest?.PageCount;
		UiTheme.DrawText((num3.HasValue && num3.GetValueOrDefault() > 0) ? $"Page {latest.Page ?? Math.Min(latest.CompletedPages.GetValueOrDefault() + 1, latest.PageCount.Value)} of {latest.PageCount}" : FriendlyStage(latest?.Stage), (int)(bounds.X + 30f * scale), (int)(bounds.Y + 155f * scale), Math.Max(13, (int)(16f * scale)), UiTheme.Muted);
		Rectangle bounds2 = new Rectangle(bounds.X + 30f * scale, bounds.Y + 192f * scale, bounds.Width - 60f * scale, 18f * scale);
		bool animated = !cancelling && latest?.Stage == "page_inference" && latest.Status == "started";
		UiTheme.DrawProgressBar(bounds2, model.Fraction, animated, model.ElapsedSeconds);
		UiTheme.DrawText($"{model.Fraction * 100.0:0}%", (int)(bounds2.X + bounds2.Width - 42f * scale), (int)(bounds2.Y + 28f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Muted);
		string text = "Elapsed  " + PlaybackFormatting.FormatTime(model.ElapsedSeconds);
		bool flag;
		switch (latest?.Stage)
		{
		case "normalization":
		case "midi_write":
		case "cache_validation":
			flag = true;
			break;
		default:
			flag = false;
			break;
		}
		object text2;
		if (!flag)
		{
			double? estimatedRemainingSeconds = model.EstimatedRemainingSeconds;
			if (estimatedRemainingSeconds.HasValue)
			{
				double valueOrDefault = estimatedRemainingSeconds.GetValueOrDefault();
				text2 = "Approx. remaining  " + PlaybackFormatting.FormatTime(valueOrDefault);
			}
			else
			{
				text2 = "Estimating…";
			}
		}
		else
		{
			text2 = "Finishing…";
		}
		UiTheme.DrawText(text, (int)(bounds.X + 30f * scale), (int)(bounds.Y + 244f * scale), Math.Max(13, (int)(15f * scale)), UiTheme.Muted);
		int num4 = UiTheme.MeasureText((string)text2, Math.Max(13, (int)(15f * scale)));
		UiTheme.DrawText((string)text2, (int)(bounds.X + bounds.Width - 30f * scale - (float)num4), (int)(bounds.Y + 244f * scale), Math.Max(13, (int)(15f * scale)), UiTheme.Muted);
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
		float num = Math.Min((float)layout.Width - 64f * scale, 760f * scale);
		float num2 = 390f * scale;
		Rectangle bounds = new Rectangle(((float)layout.Width - num) / 2f, ((float)layout.Height - num2) / 2f, num, num2);
		UiTheme.DrawCard(bounds, scale);
		UiTheme.DrawText("Conversion failed", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 26f * scale), Math.Max(24, (int)(30f * scale)), UiTheme.Danger);
		DrawWrappedText(FormatLoadError(exception ?? new InvalidOperationException("Unknown loading error.")), new Rectangle(bounds.X + 30f * scale, bounds.Y + 82f * scale, bounds.Width - 60f * scale, 110f * scale), Math.Max(14, (int)(17f * scale)), UiTheme.Text);
		if (exception is KnownOmrFailureException)
		{
			UiTheme.DrawText("This deterministic result was remembered; the model was not loaded again.", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 205f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Warning);
			goto IL_01cc;
		}
		if (!(exception is OmrPipelineException ex))
		{
			goto IL_0189;
		}
		switch (ex.ErrorCode)
		{
		case "NORMALIZATION_FAILED":
		case "MUSICXML_PARSE_FAILED":
			break;
		default:
			goto IL_0189;
		}
		bool flag = true;
		goto IL_018c;
		IL_0189:
		flag = false;
		goto IL_018c;
		IL_01cc:
		float y = bounds.Y + bounds.Height - 116f * scale;
		float num3 = 10f * scale;
		float num4 = (bounds.Width - 60f * scale - num3 * 2f) / 3f;
		if (request?.InputPath != null)
		{
			string label = ((request.Engine == OmrEngine.Zeus) ? "Retry homr" : "Retry Zeus");
			Color accent = ((request.Engine == OmrEngine.Zeus) ? UiTheme.Lime : UiTheme.Sky);
			if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale, y, num4, 44f * scale), label, accent))
			{
				return ErrorAction.RetryAlternate;
			}
			if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale + num4 + num3, y, num4, 44f * scale), "Retry anyway", UiTheme.Warning))
			{
				return ErrorAction.RetrySame;
			}
			if (UiTheme.DrawButton(new Rectangle(bounds.X + 30f * scale + (num4 + num3) * 2f, y, num4, 44f * scale), "Choose file", UiTheme.Sky))
			{
				return ErrorAction.ChooseFile;
			}
		}
		else if (UiTheme.DrawButton(new Rectangle(bounds.X + bounds.Width / 2f - 100f * scale, y, 200f * scale, 44f * scale), "Back to library", UiTheme.Sky))
		{
			return ErrorAction.Back;
		}
		return ErrorAction.None;
		IL_018c:
		if (flag)
		{
			UiTheme.DrawText("The engine could not preserve a reliable score structure. Try the other engine.", (int)(bounds.X + 30f * scale), (int)(bounds.Y + 205f * scale), Math.Max(12, (int)(14f * scale)), UiTheme.Warning);
		}
		goto IL_01cc;
	}

	private static void DrawWrappedText(string text, Rectangle bounds, int fontSize, Color color)
	{
		string[] array = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
		string text2 = string.Empty;
		float num = bounds.Y;
		string[] array2 = array;
		foreach (string text3 in array2)
		{
			string text4 = ((text2.Length == 0) ? text3 : (text2 + " " + text3));
			if ((float)UiTheme.MeasureText(text4, fontSize) > bounds.Width && text2.Length > 0)
			{
				UiTheme.DrawText(text2, (int)bounds.X, (int)num, fontSize, color);
				num += (float)(fontSize + 7);
				text2 = text3;
				if (num + (float)fontSize > bounds.Y + bounds.Height)
				{
					break;
				}
			}
			else
			{
				text2 = text4;
			}
		}
		if (text2.Length > 0 && num + (float)fontSize <= bounds.Y + bounds.Height)
		{
			UiTheme.DrawText(text2, (int)bounds.X, (int)num, fontSize, color);
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
			if (!sliderDragging && (bool)Raylib.IsMouseButtonPressed(MouseButton.Left) && (bool)Raylib.CheckCollisionPointRec(mousePosition, rec))
			{
				sliderDragging = true;
				resumeAfterSlider = playback.IsPlaying;
				sliderPreviewPosition = PlaybackFormatting.PositionFromSlider(mousePosition.X, playbackSlider.X, playbackSlider.Width, playback.Session.TotalDuration);
				playback.Pause();
			}
			else if (sliderDragging && (bool)Raylib.IsMouseButtonDown(MouseButton.Left))
			{
				sliderPreviewPosition = PlaybackFormatting.PositionFromSlider(mousePosition.X, playbackSlider.X, playbackSlider.Width, playback.Session.TotalDuration);
			}
			if (sliderDragging && (bool)Raylib.IsMouseButtonReleased(MouseButton.Left))
			{
				playback.CommitSilencedSeek(sliderPreviewPosition, resumeAfterSlider);
				sliderDragging = false;
				state = (playback.IsCompleted ? GameState.Completed : GameState.Playing);
			}
			if (!sliderDragging && (bool)Raylib.IsKeyPressed(KeyboardKey.Space))
			{
				TogglePlayback(playback, ref state);
			}
			if (!sliderDragging && (bool)Raylib.IsKeyPressed(KeyboardKey.Left))
			{
				SeekRelative(playback, -5.0, ref state);
			}
			if (!sliderDragging && (bool)Raylib.IsKeyPressed(KeyboardKey.Right))
			{
				SeekRelative(playback, 5.0, ref state);
			}
		}
	}

	private static Rectangle GetPlaybackSlider(UiLayout layout)
	{
		float num = Math.Clamp(118f * layout.Scale, 90f, 180f);
		return new Rectangle(num, (float)layout.HeaderHeight - 23f * layout.Scale, (float)layout.Width - num * 2f, Math.Max(8f, 10f * layout.Scale));
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
		UiTheme.DrawBadge(new Rectangle((float)layout.Width - 190f * scale, 14f * scale, 74f * scale, 30f * scale), OmrPipeline.GetEngineName(song.Engine).ToUpperInvariant(), accent);
		if (song.LoadedFromCache)
		{
			UiTheme.DrawBadge(new Rectangle((float)layout.Width - 108f * scale, 14f * scale, 88f * scale, 30f * scale), "CACHE", UiTheme.Muted);
		}
		UiTheme.DrawText($"{song.NoteCount:N0} notes", (int)(106f * scale), (int)(46f * scale), Math.Max(11, (int)(13f * scale)), UiTheme.Muted);
		float num = (float)layout.Width / 2f - 92f * scale;
		if (UiTheme.DrawButton(new Rectangle(num, 10f * scale, 52f * scale, 38f * scale), "−5", UiTheme.Sky))
		{
			SeekRelative(playback, -5.0, ref state);
		}
		if (UiTheme.DrawButton(new Rectangle(num + 62f * scale, 7f * scale, 60f * scale, 44f * scale), playback.IsPlaying ? "Pause" : "Play", UiTheme.Sky))
		{
			TogglePlayback(playback, ref state);
		}
		if (UiTheme.DrawButton(new Rectangle(num + 132f * scale, 10f * scale, 52f * scale, 38f * scale), "+5", UiTheme.Sky))
		{
			SeekRelative(playback, 5.0, ref state);
		}
		DrawPlaybackRateControl(playback, rateEditor, layout);
		Rectangle playbackSlider = GetPlaybackSlider(layout);
		double num2 = (sliderDragging ? sliderPreviewPosition : playback.Position);
		double num3 = ((playback.Session.TotalDuration > 0.0) ? Math.Clamp(num2 / playback.Session.TotalDuration, 0.0, 1.0) : 0.0);
		UiTheme.DrawProgressBar(playbackSlider, num3, animated: false, 0.0);
		Raylib.DrawCircle((int)(playbackSlider.X + (float)(num3 * (double)playbackSlider.Width)), (int)(playbackSlider.Y + playbackSlider.Height / 2f), Math.Max(7f, 8f * scale), UiTheme.Text);
		string text = PlaybackFormatting.FormatTime(num2) + " / " + PlaybackFormatting.FormatTime(playback.Session.TotalDuration);
		int fontSize = Math.Max(12, (int)(14f * scale));
		UiTheme.DrawText(text, (int)((float)layout.Width / 2f - (float)UiTheme.MeasureText(text, fontSize) / 2f), (int)(playbackSlider.Y + 15f * scale), fontSize, UiTheme.Muted);
		Vector2 mousePosition = Raylib.GetMousePosition();
		Rectangle rec = new Rectangle(playbackSlider.X - 8f, playbackSlider.Y - 16f, playbackSlider.Width + 16f, 42f);
		if (!sliderDragging && (bool)Raylib.CheckCollisionPointRec(mousePosition, rec))
		{
			UiTheme.DrawText(PlaybackFormatting.FormatTime(PlaybackFormatting.PositionFromSlider(mousePosition.X, playbackSlider.X, playbackSlider.Width, playback.Session.TotalDuration)), Math.Clamp((int)mousePosition.X - 24, (int)playbackSlider.X, (int)(playbackSlider.X + playbackSlider.Width - 48f)), (int)(playbackSlider.Y + 34f * scale), fontSize, UiTheme.Text);
		}
		for (int i = 0; i < piano.Keys.Length; i++)
		{
			piano.Keys[i].IsPressed = !sliderDragging && playback.IsKeyActive(i);
			PianoKey pianoKey = piano.Keys[i];
			if (!pianoKey.IsBlack)
			{
				Raylib.DrawLine(pianoKey.X, layout.HeaderHeight, pianoKey.X, layout.HitLineY, new Color((int)UiTheme.Border.R, (int)UiTheme.Border.G, (int)UiTheme.Border.B, 72));
			}
		}
		double lookAhead = Math.Max(1.0, (double)(layout.HitLineY - layout.HeaderHeight) / layout.FallSpeed + 1.0);
		(int Start, int End) visibleRange = playback.Session.GetVisibleRange(num2, 1.0, lookAhead);
		int item = visibleRange.Start;
		int item2 = visibleRange.End;
		for (int j = item; j < item2; j++)
		{
			Note note = playback.Session.Notes[j];
			PianoKey key = piano.Keys[note.TargetKeyIndex];
			int num4 = layout.HitLineY - (int)Math.Floor((note.StartTime - num2) * layout.FallSpeed);
			int num5 = Math.Max(1, (int)(note.Duration * layout.FallSpeed));
			int num6 = num4 - num5;
			if (num6 <= layout.Height && num4 >= layout.HeaderHeight)
			{
				DrawFallingNote(note, key, num6, num4, scale);
			}
		}
		piano.Draw();
		if (sliderDragging)
		{
			UiTheme.DrawText("SEEK PREVIEW", layout.Width / 2 - 68, layout.HeaderHeight + 12, Math.Max(14, (int)(17f * scale)), UiTheme.Warning);
		}
		else if (!playback.IsPlaying)
		{
			string text2 = ((state == GameState.Completed) ? "COMPLETED" : "PAUSED");
			int fontSize2 = Math.Max(24, (int)(34f * scale));
			UiTheme.DrawText(text2, layout.Width / 2 - UiTheme.MeasureText(text2, fontSize2) / 2, layout.HeaderHeight + 18, fontSize2, UiTheme.Warning);
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
		float num = 26f * scale;
		float width = 64f * scale;
		float height = 26f * scale;
		float x = (float)layout.Width - 16f * scale - (2f * num + width + 10f * scale);
		float y = (float)layout.HitLineY - height - 12f * scale;
		int current = (int)Math.Round(playback.AudioOffsetSeconds * 1000.0);
		int num2 = Math.Max(10, (int)(12f * scale));
		UiTheme.DrawText("AUDIO OFFSET", (int)(x - (float)UiTheme.MeasureText("AUDIO OFFSET", num2) - 10f * scale), (int)(y + (height - (float)num2) / 2f), num2, UiTheme.Muted);
		if (UiTheme.DrawButton(new Rectangle(x, y, num, height), "−", UiTheme.Muted, !editor.IsEditing && current > AppSettingsStore.MinimumAudioOffsetMilliseconds))
		{
			editor.Cancel();
			StepAudioOffset(playback, -AudioOffsetRules.StepMilliseconds);
		}
		Rectangle rec = new Rectangle(x + num + 5f * scale, y, width, height);
		Raylib.DrawRectangleRounded(rec, 0.16f, 8, UiTheme.Elevated);
		Color color = ((editor.Error != null) ? UiTheme.Danger : (editor.IsEditing ? UiTheme.Sky : UiTheme.Border));
		Raylib.DrawRectangleRoundedLinesEx(rec, 0.16f, 8, Math.Max(1f, scale), color);
		if ((bool)Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			int committed;
			if ((bool)Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), rec))
			{
				if (!editor.IsEditing)
				{
					editor.Begin(current);
				}
			}
			else if (editor.IsEditing && editor.TryCommit(out committed))
			{
				ApplyAudioOffset(playback, committed);
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
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.Backspace))
			{
				editor.Backspace();
			}
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.Enter) && editor.TryCommit(out var committed2))
			{
				ApplyAudioOffset(playback, committed2);
			}
			else if ((bool)Raylib.IsKeyPressed(KeyboardKey.Escape))
			{
				editor.Cancel();
			}
		}
		string text = (editor.IsEditing ? (editor.Text + "|") : $"{current} ms");
		int num3 = Math.Max(11, (int)(13f * scale));
		UiTheme.DrawText(text, (int)(rec.X + (rec.Width - (float)UiTheme.MeasureText(text, num3)) / 2f), (int)(rec.Y + (rec.Height - (float)num3) / 2f), num3, UiTheme.Text);
		if (UiTheme.DrawButton(new Rectangle(rec.X + rec.Width + 5f * scale, y, num, height), "+", UiTheme.Muted, !editor.IsEditing && current < AppSettingsStore.MaximumAudioOffsetMilliseconds))
		{
			editor.Cancel();
			StepAudioOffset(playback, AudioOffsetRules.StepMilliseconds);
		}
		if (editor.Error != null)
		{
			UiTheme.DrawText(editor.Error, (int)rec.X, (int)(rec.Y + rec.Height + 2f * scale), Math.Max(9, (int)(11f * scale)), UiTheme.Danger);
		}
	}

	private static void StepAudioOffset(PlaybackController playback, int deltaMilliseconds)
	{
		int current = (int)Math.Round(playback.AudioOffsetSeconds * 1000.0);
		ApplyAudioOffset(playback, AppSettingsStore.Clamp(current + deltaMilliseconds));
	}

	/// <summary>Applies the offset and persists it, so calibration survives a restart.</summary>
	private static void ApplyAudioOffset(PlaybackController playback, int milliseconds)
	{
		int updated = AppSettingsStore.Clamp(milliseconds);
		if (updated != (int)Math.Round(playback.AudioOffsetSeconds * 1000.0))
		{
			playback.SetAudioOffsetSeconds((double)updated / 1000.0);
			AppSettingsStore.SaveAudioOffsetMilliseconds(updated);
		}
	}

	private static void DrawPlaybackRateControl(PlaybackController playback, PlaybackRateEditor editor, UiLayout layout)
	{
		float scale = layout.Scale;
		float num = (float)layout.Width - 400f * scale;
		float y = 12f * scale;
		float num2 = 32f * scale;
		float width = 72f * scale;
		float height = 34f * scale;
		bool enabled = playback.PlaybackRate > 0.050000001;
		bool enabled2 = playback.PlaybackRate < 1.999999999;
		if (UiTheme.DrawButton(new Rectangle(num, y, num2, height), "−", UiTheme.Muted, enabled))
		{
			editor.Cancel();
			StepPlaybackRate(playback, -1);
		}
		Rectangle rec = new Rectangle(num + num2 + 5f * scale, y, width, height);
		Raylib.DrawRectangleRounded(rec, 0.16f, 8, UiTheme.Elevated);
		Color color = ((editor.Error != null) ? UiTheme.Danger : (editor.IsEditing ? UiTheme.Sky : UiTheme.Border));
		Raylib.DrawRectangleRoundedLinesEx(rec, 0.16f, 8, Math.Max(1f, scale), color);
		if ((bool)Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			double rate;
			if ((bool)Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), rec))
			{
				if (!editor.IsEditing)
				{
					editor.Begin(playback.PlaybackRate);
				}
			}
			else if (editor.IsEditing && editor.TryCommit(out rate))
			{
				playback.SetPlaybackRate(rate);
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
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.Backspace))
			{
				editor.Backspace();
			}
			if ((bool)Raylib.IsKeyPressed(KeyboardKey.Enter) && editor.TryCommit(out var rate2))
			{
				playback.SetPlaybackRate(rate2);
			}
			else if ((bool)Raylib.IsKeyPressed(KeyboardKey.Escape))
			{
				editor.Cancel();
			}
		}
		string text = (editor.IsEditing ? (editor.Text + "|") : $"{playback.PlaybackRate:0.00}x");
		int num3 = Math.Max(11, (int)(14f * scale));
		UiTheme.DrawText(text, (int)(rec.X + (rec.Width - (float)UiTheme.MeasureText(text, num3)) / 2f), (int)(rec.Y + (rec.Height - (float)num3) / 2f), num3, UiTheme.Text);
		if (UiTheme.DrawButton(new Rectangle(rec.X + rec.Width + 5f * scale, y, num2, height), "+", UiTheme.Muted, enabled2))
		{
			editor.Cancel();
			StepPlaybackRate(playback, 1);
		}
		if (editor.Error != null)
		{
			UiTheme.DrawText(editor.Error, (int)rec.X, (int)(rec.Y + rec.Height + 2f * scale), Math.Max(9, (int)(11f * scale)), UiTheme.Danger);
		}
	}

	private static void StepPlaybackRate(PlaybackController playback, int direction)
	{
		playback.SetPlaybackRate(PlaybackRateRules.Step(playback.PlaybackRate, direction));
	}

	private static void DrawFallingNote(Note note, PianoKey key, int rawTopY, int rawBottomY, float scale)
	{
		float num = Math.Clamp(3f * scale, 2f, 5f);
		// The bottom edge is the note's actual moment, so it is not inset: insetting it
		// held every note a pixel or two short of the hit line, which reads as the whole
		// field sitting high. Only the top is pulled in, to leave a gap between notes.
		float num3 = (float)rawBottomY;
		float height = Math.Max(7f * scale, num3 - ((float)rawTopY + num));
		// Short notes grow upward from the hit line rather than downward past it, so a
		// clamped note still lands at the right time.
		float num2 = num3 - height;
		float num4 = Math.Max(20f * scale, (float)key.Width - 2f * scale);
		float x = (float)key.X + (float)key.Width / 2f - num4 / 2f;
		Rectangle rec = new Rectangle(x, num2, num4, height);
		Raylib.DrawRectangleRounded(rec, 0.24f, 8, note.Color);
		Raylib.DrawRectangleRoundedLinesEx(color: new Color(Math.Max(0, note.Color.R - 55), Math.Max(0, note.Color.G - 55), Math.Max(0, note.Color.B - 55), 255), rec: rec, roundness: 0.24f, segments: 8, lineThick: Math.Max(1f, 1.5f * scale));
		string pitchClass = note.PitchClass;
		int num5 = Math.Clamp((int)(13f * scale), 9, 16);
		while (num5 > 8 && (float)UiTheme.MeasureText(pitchClass, num5) > rec.Width - 3f * scale)
		{
			num5--;
		}
		int num6 = UiTheme.MeasureText(pitchClass, num5);
		int num7 = (int)(rec.X + (rec.Width - (float)num6) / 2f);
		int num8 = (int)(rec.Y + (rec.Height - (float)num5) / 2f);
		UiTheme.DrawText(pitchClass, num7 + 1, num8 + 1, num5, new Color(0, 0, 0, 210));
		UiTheme.DrawText(pitchClass, num7, num8, num5, UiTheme.Text);
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
			string text = ((!ex.Page.HasValue) ? string.Empty : $" on page {ex.Page}");
			bool flag;
			switch (ex.ErrorCode)
			{
			case "NORMALIZATION_FAILED":
			case "MUSICXML_PARSE_FAILED":
				flag = true;
				break;
			default:
				flag = false;
				break;
			}
			if (!flag)
			{
				return $"{ex.ErrorCode} ({ex.Stage ?? "unknown stage"}){text}: {ex.Message}";
			}
			return "The engine produced an unreliable MusicXML structure" + text + ": " + ex.Message;
		}
		if (exception.Message.Length > 240)
		{
			return exception.Message.Substring(0, 240) + "...";
		}
		return exception.Message;
	}
}
