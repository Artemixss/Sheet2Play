using System.Numerics;
using Raylib_cs;
using Color = Raylib_cs.Color;
using Rectangle = Raylib_cs.Rectangle;

namespace SynthesiaClone;

/// <summary>
/// The TEMPO panel on the playback screen: the song's start tempo and its tempo changes by bar,
/// saved per song (<see cref="TempoMapStore"/>) and applied to the playing session without
/// reloading it. HOMR reads no tempo marks, so without this every PDF plays at 120.
/// </summary>
internal static partial class Program
{
	/// <summary>Change rows shown at once above the panel; more scroll with the mouse wheel.</summary>
	private const int TempoListRows = 6;

	/// <summary>Printed-mark rows shown at once above the changes.</summary>
	private const int PrintedListRows = 5;

	/// <summary>The playing song's stored map, or null when it plays its score's marks.</summary>
	private static SongTempoMap? tempoMap;

	/// <summary>What the song plays without a map, as a map: its score's marks, or 120. Editing starts here.</summary>
	private static SongTempoMap? tempoScoreMap;

	/// <summary>The source the two maps above were read for.</summary>
	private static string? tempoMapSource;

	/// <summary>
	/// The score they were read for. The 480 and 465 conversions of one PDF share a source but not
	/// their measures, so the score map is rebuilt when the score changes.
	/// </summary>
	private static SongPerformance? tempoMapPerformance;

	/// <summary>The tempo the playing session was built with, to map its position on a change.</summary>
	private static TempoOverride? sessionTempo;

	/// <summary>Set by an edit; acted on by the main loop, which owns the audio output.</summary>
	private static bool tempoChanged;

	/// <summary>A map was saved since the library was listed, so its durations are stale.</summary>
	private static bool tempoMapsEdited;

	/// <summary>Whether the panel is showing. Closed at every start, like EXPRESSION.</summary>
	private static bool tempoPanelOpen;

	/// <summary>Where the controls right of the TEMPO button start for this song: its widest so far.</summary>
	private static SongLoadResult? tempoRowSong;

	private static float tempoRowX;

	private static int tempoListScroll;

	/// <summary>Why the last edit was not saved, shown in the panel until the next edit.</summary>
	private static string? tempoStatus;

	private static readonly TempoEditor tempoEditor = new();

	/// <summary>The marks printed in the playing song's PDF, in its measures; null until they are read.</summary>
	private static IReadOnlyList<PrintedMark>? tempoPrinted;

	/// <summary>The printed marks the user ignored for the playing song (<see cref="DetectedMark.Key"/>).</summary>
	private static IReadOnlySet<string> tempoIgnored = new HashSet<string>();

	/// <summary>
	/// What the playing song plays without a map of the user's: its printed marks but the ignored
	/// ones, or null when it has none it can use.
	/// </summary>
	private static SongTempoMap? tempoPrintedMap;

	/// <summary>Whether the printed marks are listed. Closed for every song, like the panel.</summary>
	private static bool tempoPrintedOpen;

	private static int tempoPrintedScroll;

	/// <summary>The PDF's pages, and those on which the reader found no staff and so read nothing.</summary>
	private static int tempoPrintedPages;

	private static int tempoPrintedBlindPages;

	/// <summary>The reading READ PRINTED MARKS started, while it runs, and the song it reads.</summary>
	private static Task<DetectedTempos>? tempoReading;

	private static string? tempoReadingSource;

	/// <summary>The page the reading has finished and its page count, written by the reader's thread.</summary>
	private static int tempoReadingPage;

	private static int tempoReadingPages;

	/// <summary>The bridge reader's hash, which stored marks must have been read with.</summary>
	private static string? tempoReaderSha;

	/// <summary>Where the field being typed into was drawn last frame, so a click elsewhere commits it.</summary>
	private static Rectangle tempoEditBox;

	/// <summary>
	/// The tempo <paramref name="song"/> plays at: the user's map, else the marks printed in its PDF;
	/// null plays its score.
	/// </summary>
	private static TempoOverride? TempoFor(SongLoadResult song)
	{
		LoadTempoMap(song);
		return SongTempoMaps.Override(tempoMap ?? tempoPrintedMap, song.Performance);
	}

	/// <summary>The same tempo, read fresh, for the bench and offline render.</summary>
	internal static TempoOverride? StoredTempo(SongLoadResult song)
	{
		if (song.SourceSha256 is not string source || song.Performance is null)
		{
			return null;
		}
		try
		{
			SongTempoMap? map = TempoMapStore.Get(source) ?? TempoDetection.PrintedMap(SongCache.ApplicationDirectory,
				TempoDetection.ReaderSha256(OmrPipeline.DefaultBridgeDirectory), source, song.Performance, song.Engine,
				TempoMapStore.GetIgnoredMarks(source));
			return SongTempoMaps.Override(map, song.Performance);
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException)
		{
			Console.Error.WriteLine("[TEMPO] The tempo map was not read: " + error.Message);
			return null;
		}
	}

	private static void LoadTempoMap(SongLoadResult song)
	{
		if (song.SourceSha256 == tempoMapSource && ReferenceEquals(song.Performance, tempoMapPerformance))
		{
			return;
		}
		tempoMapSource = song.SourceSha256;
		tempoMapPerformance = song.Performance;
		tempoMap = null;
		tempoScoreMap = null;
		tempoStatus = null;
		tempoListScroll = 0;
		tempoEditor.Cancel();
		if (song.SourceSha256 is null || song.Performance is not SongPerformance performance)
		{
			return;
		}
		tempoScoreMap = SongTempoMaps.FromScore(performance, song.Engine);
		try
		{
			tempoMap = TempoMapStore.Get(song.SourceSha256);
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException)
		{
			Console.Error.WriteLine("[TEMPO] The tempo map was not read: " + error.Message);
		}
		LoadPrintedMarks(song.SourceSha256, performance);
		RefreshPrintedMap(performance, song.Engine);
	}

	/// <summary>Rebuilds what the song plays from its printed marks, after they were read or one was ignored.</summary>
	private static void RefreshPrintedMap(SongPerformance performance, OmrEngine engine)
	{
		SongTempoMap? previous = tempoPrintedMap;
		tempoPrintedMap = tempoPrinted is null ? null : TempoDetection.PrintedMap(tempoPrinted, tempoIgnored, performance, engine);
		// Without a map of the user's, the printed marks are what plays, so the session follows them.
		if (tempoMap is null && !Equals(SongTempoMaps.Override(previous, performance), SongTempoMaps.Override(tempoPrintedMap, performance)))
		{
			tempoChanged = true;
		}
	}

	/// <summary>The song's printed marks as stored for the bridge's reader, and the ones the user ignored.</summary>
	private static void LoadPrintedMarks(string source, SongPerformance performance)
	{
		tempoPrinted = null;
		tempoPrintedMap = null;
		tempoPrintedPages = 0;
		tempoPrintedBlindPages = 0;
		tempoPrintedOpen = false;
		tempoPrintedScroll = 0;
		tempoIgnored = new HashSet<string>();
		if (performance.Kind != "omr-pages")
		{
			return;
		}
		tempoReaderSha ??= TempoDetection.ReaderSha256(OmrPipeline.DefaultBridgeDirectory);
		if (TempoDetection.Load(SongCache.ApplicationDirectory, source, tempoReaderSha) is DetectedTempos detected)
		{
			ShowPrintedMarks(detected, performance);
		}
		try
		{
			tempoIgnored = TempoMapStore.GetIgnoredMarks(source);
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException)
		{
			Console.Error.WriteLine("[TEMPO] The ignored marks were not read: " + error.Message);
		}
	}

	/// <summary>
	/// Reads the song's PDF in the background, at low priority so playback keeps the CPU. The PDF is
	/// the library's copy the song was converted from, found by its hash.
	/// </summary>
	private static void StartReadingPrintedMarks(SongLoadResult song)
	{
		string source = song.SourceSha256!;
		tempoReadingSource = source;
		tempoReadingPage = 0;
		tempoReadingPages = 0;
		tempoStatus = null;
		IProgress<(int Page, int Pages)> progress = new ReadingProgress();
		tempoReading = Task.Run(() =>
		{
			string pdf = SongCache.FindSource(song) is string found && found.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase)
				? found
				: throw new TempoDetectionException("its PDF is no longer in the library");
			return TempoDetection.Detect(SongCache.ApplicationDirectory, OmrPipeline.DefaultBridgeDirectory, pdf, source,
				progress, background: true);
		});
		Console.Error.WriteLine($"[TEMPO] {song.DisplayName}: reading the printed marks");
	}

	private sealed class ReadingProgress : IProgress<(int Page, int Pages)>
	{
		public void Report((int Page, int Pages) value)
		{
			Volatile.Write(ref tempoReadingPages, value.Pages);
			Volatile.Write(ref tempoReadingPage, value.Page);
		}
	}

	private static void ShowPrintedMarks(DetectedTempos detected, SongPerformance performance)
	{
		tempoPrinted = TempoDetection.Place(detected, performance);
		tempoPrintedPages = detected.Pages.Count;
		tempoPrintedBlindPages = detected.Pages.Count(static page => page.Systems == 0);
	}

	/// <summary>Takes in a finished reading: the marks when it was for the playing song, else just its outcome.</summary>
	private static void CollectPrintedMarks(SongLoadResult song, SongPerformance performance)
	{
		if (tempoReading is not { IsCompleted: true } reading)
		{
			return;
		}
		tempoReading = null;
		bool current = tempoReadingSource == song.SourceSha256;
		if (reading.IsCompletedSuccessfully)
		{
			Console.Error.WriteLine($"[TEMPO] printed marks read: {reading.Result.Marks.Count} for {tempoReadingSource}");
			if (current)
			{
				ShowPrintedMarks(reading.Result, performance);
				RefreshPrintedMap(performance, song.Engine);
				tempoPrintedOpen = true;
				tempoPrintedScroll = 0;
				tempoMapsEdited = true;
			}
			return;
		}
		Exception error = reading.Exception?.GetBaseException() ?? new TempoDetectionException("cancelled");
		Console.Error.WriteLine("[TEMPO] The printed marks were not read: " + error.Message);
		if (current)
		{
			tempoStatus = "Marks not read: " + error.Message;
		}
	}

	/// <summary>Saves (or with null, removes) the song's map and asks the main loop to re-time the session.</summary>
	private static void SaveTempoMap(SongLoadResult song, SongTempoMap? map)
	{
		tempoMap = map;
		tempoStatus = null;
		tempoChanged = true;
		tempoMapsEdited = true;
		try
		{
			if (map is null)
			{
				TempoMapStore.Remove(song.SourceSha256!);
			}
			else
			{
				TempoMapStore.Save(song.SourceSha256!, map);
			}
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException
			or ArgumentException)
		{
			tempoStatus = "Not saved: " + error.Message;
			Console.Error.WriteLine("[TEMPO] The tempo map was not saved: " + error.Message);
		}
		Console.Error.WriteLine($"[TEMPO] {song.DisplayName}: {(map is null ? "reset to the score or its printed marks" : DescribeMap(map))}");
	}

	private static string DescribeMap(SongTempoMap map) =>
		$"start {TempoRules.Format(map.Start.Bpm)} {map.Start.Unit}" +
		string.Concat(map.Changes.Select(static change =>
			$", measure {change.Measure} {TempoRules.Format(change.Tempo.Bpm)} {change.Tempo.Unit}"));

	private static string DescribeTempo(TempoOverride? tempo) =>
		tempo is null ? "score" : $"{tempo.StartQuarterBpm:0.##}+{tempo.Changes.Count}";

	private static IReadOnlyList<BarTempo> Sorted(IEnumerable<BarTempo> changes) =>
		changes.OrderBy(static change => change.Measure).ThenBy(static change => change.Offset).ToArray();

	/// <summary>
	/// The TEMPO button, bottom-left above EXPRESSION, and when it is open the start tempo, RESET
	/// and "+ CHANGE AT BAR N" to its right, with the song's changes listed above. The button always
	/// says the tempo of the bar playing, and in the warning colour when the song is on the 120
	/// fallback, so a song that has no real tempo yet is never hidden behind a closed panel.
	/// </summary>
	private static void DrawTempoPanel(SongLoadResult song, double position, UiLayout layout)
	{
		float scale = layout.Scale;
		float height = 26f * scale;
		float y = (float)layout.HitLineY - 3f * height - 28f * scale;
		float x = 16f * scale;

		// Songs without a score keep the tempo they came with: a MIDI file's own, or a legacy cache's
		// 120 until it is re-converted into a song that keeps its score.
		if (song.Performance is not SongPerformance performance || song.SourceSha256 is null)
		{
			DrawPanelAction(ref x, y, height,
				OmrEngines.RunsOmr(song.Engine) ? "TEMPO · RE-CONVERT TO SET" : "TEMPO · FROM THE FILE",
				UiTheme.Muted, enabled: false, scale);
			return;
		}

		LoadTempoMap(song);
		CollectPrintedMarks(song, performance);
		SongTempoMap shown = tempoMap ?? tempoPrintedMap ?? tempoScoreMap!;
		bool changesApply = SongTempoMaps.ChangesApply(shown, performance);
		bool printed = tempoMap is null && tempoPrintedMap is not null;
		bool fallback = tempoMap is null && !printed && performance.Tempos.All(static tempo => tempo.QuarterBpm is null);
		int changeCount = changesApply ? shown.Changes.Count : 0;
		string suffix = fallback
			? " · DEFAULT"
			: printed
				? " · PRINTED" + (changeCount > 0 ? $" · {changeCount} CHANGE{(changeCount == 1 ? "" : "S")}" : "")
			: !changesApply
				? " · CHECK BARS"
				: changeCount > 0 ? $" · {changeCount} CHANGE{(changeCount == 1 ? "" : "S")}" : "";
		// The tempo playing now rather than the start tempo, so a change at bar 37 to 111 shows as 111
		// while bar 37 plays.
		int barIndex = songOverlay.BarIndexAt(position);
		TempoMark playing = changesApply && barIndex >= 0
			? SongTempoMaps.TempoAt(shown, songOverlay.Bars[barIndex].Measure)
			: shown.Start;
		if (DrawPanelButton(ref x, y, height, "TEMPO  ", fallback || !changesApply ? UiTheme.Warning : UiTheme.Text,
			tempoPanelOpen, scale, playing.Unit, "=" + TempoRules.Format(playing.Bpm) + suffix))
		{
			tempoPanelOpen = !tempoPanelOpen;
			tempoEditor.Cancel();
		}
		// The button's width follows the tempo; the controls right of it keep the widest it has been
		// for this song, so they do not jump back and forth as it plays.
		x = ReferenceEquals(tempoRowSong, song) ? Math.Max(x, tempoRowX) : x;
		(tempoRowSong, tempoRowX) = (song, x);
		if (!tempoPanelOpen)
		{
			return;
		}

		// Every control below edits what the ones before it left, so two edits in one frame (a typed
		// value committed by clicking another row's +) both land.
		SongTempoMap? edited = null;
		HandleTempoTyping(shown, ref edited);

		// The start tempo, then RESET, then the bar playing now, whose label changes as it plays and
		// so goes last, where its width moves nothing.
		if (DrawTempoField(ref x, y, height, -1, shown.Start, scale) is TempoMark start)
		{
			edited = (edited ?? shown) with { Start = start };
		}
		x += 4f * scale;
		if (DrawPanelAction(ref x, y, height, "RESET", UiTheme.Warning, tempoMap is not null, scale))
		{
			tempoEditor.Cancel();
			SaveTempoMap(song, null);
			return;
		}
		DrawPrintedAction(song, performance, ref x, y, height, scale);
		if (barIndex >= 0)
		{
			OverlayBar bar = songOverlay.Bars[barIndex];
			bool taken = shown.Changes.Any(change => change.Measure == bar.Measure);
			string label = bar.Measure == 0 ? $"BAR {bar.Number} · START"
				: taken ? $"BAR {bar.Number} · HAS A CHANGE"
				: $"+ CHANGE AT BAR {bar.Number}";
			if (DrawPanelAction(ref x, y, height, label, UiTheme.Lime, changesApply && bar.Measure > 0 && !taken, scale))
			{
				SongTempoMap basis = edited ?? shown;
				BarTempo added = new(bar.Measure, 0, SongTempoMaps.TempoAt(basis, bar.Measure));
				edited = basis with { Changes = Sorted(basis.Changes.Append(added)) };
				// Ready to type the new tempo straight away, in a row scrolled into view.
				int index = edited.Changes.ToList().IndexOf(added);
				tempoEditor.Begin(index, added.Tempo.Bpm);
				tempoListScroll = Math.Clamp(tempoListScroll, index - TempoListRows + 1, index);
			}
		}
		if (tempoStatus is not null || tempoEditor.Error is not null)
		{
			int labelSize = Math.Max(10, (int)(12f * scale));
			UiTheme.DrawText(tempoEditor.Error ?? tempoStatus!, (int)(x + 2f * scale), (int)(y + (height - labelSize) / 2f),
				labelSize, UiTheme.Danger);
		}

		float changesTop = DrawTempoChanges(song, performance, shown, changesApply, y, height, scale, ref edited);
		if (tempoPrintedOpen && tempoPrinted is not null)
		{
			DrawPrintedMarks(song, performance, shown, changesApply, changesTop, height, scale, ref edited);
		}

		if (edited is not null)
		{
			SaveTempoMap(song, edited with
			{
				Engine = changesApply ? song.Engine : edited.Engine,
				UpdatedUtc = DateTimeOffset.UtcNow
			});
		}
	}

	/// <summary>
	/// The changes, one row each, stacked upward from the start row with the earliest bar on top.
	/// Changes set on a conversion with a different number of bars do not play, and are listed in
	/// the warning colour with KEEP (they are right for this one too) and CLEAR. Returns the top of
	/// what it drew, <paramref name="y"/> when there are none.
	/// </summary>
	private static float DrawTempoChanges(SongLoadResult song, SongPerformance performance, SongTempoMap shown,
		bool changesApply, float y, float height, float scale, ref SongTempoMap? edited)
	{
		int count = shown.Changes.Count;
		if (count == 0)
		{
			return y;
		}
		int textSize = Math.Max(10, (int)(12f * scale));
		float rowStep = height + 6f * scale;
		int visible = Math.Min(TempoListRows, count);
		tempoListScroll = Math.Clamp(tempoListScroll, 0, count - visible);
		float left = 16f * scale;
		float top = y - visible * rowStep;
		Rectangle listArea = new Rectangle(left, top, 520f * scale, visible * rowStep);
		if (count > visible && Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), listArea))
		{
			float wheel = Raylib.GetMouseWheelMove();
			if (wheel != 0)
			{
				tempoListScroll = Math.Clamp(tempoListScroll - Math.Sign(wheel), 0, count - visible);
			}
		}
		float barLabelWidth = LabelWidth("BAR 0000", textSize) + 20f * scale;
		for (int row = 0; row < visible; row++)
		{
			int index = tempoListScroll + row;
			BarTempo change = shown.Changes[index];
			float x = left;
			float rowY = top + row * rowStep;
			string name = change.Measure < performance.Measures.Count
				? SongTempoMaps.BarName(performance, change.Measure)
				: (change.Measure + 1).ToString(System.Globalization.CultureInfo.InvariantCulture);
			DrawTempoLabel(ref x, rowY, height, barLabelWidth, "BAR " + name, changesApply ? UiTheme.Text : UiTheme.Warning,
				scale);
			if (!changesApply)
			{
				DrawTempoLabel(ref x, rowY, height, 0, null, UiTheme.Warning, scale, change.Tempo);
				continue;
			}
			if (DrawTempoField(ref x, rowY, height, index, change.Tempo, scale) is TempoMark tempo)
			{
				SongTempoMap basis = edited ?? shown;
				edited = basis with
				{
					Changes = basis.Changes.Select((existing, at) => at == index ? existing with { Tempo = tempo } : existing)
						.ToArray()
				};
			}
			x += 4f * scale;
			if (DrawPanelAction(ref x, rowY, height, "DELETE", UiTheme.Warning, enabled: true, scale))
			{
				tempoEditor.Cancel();
				SongTempoMap basis = edited ?? shown;
				edited = basis with { Changes = basis.Changes.Where((_, at) => at != index).ToArray() };
			}
		}

		float aboveY = top - rowStep;
		float note = left;
		if (count > visible)
		{
			DrawTempoLabel(ref note, aboveY, height, 0,
				$"BARS {tempoListScroll + 1}-{tempoListScroll + visible} OF {count} CHANGES · SCROLL", UiTheme.Muted, scale);
		}
		if (!changesApply)
		{
			string engine = shown.Engine switch
			{
				OmrEngine.Homr480 => "HOMR 480",
				OmrEngine.Homr465 => "HOMR 465",
				OmrEngine other => OmrPipeline.GetEngineName(other)
			};
			DrawTempoLabel(ref note, aboveY, height, 0,
				$"SET ON {engine} WITH {shown.MeasureCount} BARS; THIS HAS {performance.Measures.Count}. NOT PLAYING.",
				UiTheme.Warning, scale);
			if (DrawPanelAction(ref note, aboveY, height, "KEEP", UiTheme.Lime, enabled: true, scale))
			{
				edited = shown with
				{
					Changes = shown.Changes.Where(change => change.Measure < performance.Measures.Count).ToArray(),
					Engine = song.Engine,
					MeasureCount = performance.Measures.Count
				};
			}
			if (DrawPanelAction(ref note, aboveY, height, "CLEAR", UiTheme.Warning, enabled: true, scale))
			{
				edited = shown with { Changes = [], Engine = song.Engine, MeasureCount = performance.Measures.Count };
			}
		}
		return count > visible || !changesApply ? aboveY : top;
	}

	/// <summary>
	/// The start row's control for printed marks: READ PRINTED MARKS before the PDF was read, the
	/// reading's progress while it runs, then PRINTED, which lists them. Only PDF conversions have one.
	/// </summary>
	private static void DrawPrintedAction(SongLoadResult song, SongPerformance performance, ref float x, float y,
		float height, float scale)
	{
		if (performance.Kind != "omr-pages" || !OmrEngines.RunsOmr(song.Engine))
		{
			return;
		}
		if (tempoReading is not null)
		{
			int page = Volatile.Read(ref tempoReadingPage);
			int pages = Volatile.Read(ref tempoReadingPages);
			string label = tempoReadingSource != song.SourceSha256 ? "READING ANOTHER SONG'S MARKS"
				: pages > 0 ? $"READING MARKS · PAGE {Math.Min(page + 1, pages)} OF {pages}"
				: "READING MARKS…";
			DrawPanelAction(ref x, y, height, label, UiTheme.Muted, enabled: false, scale);
			return;
		}
		if (tempoPrinted is null)
		{
			if (DrawPanelAction(ref x, y, height, "READ PRINTED MARKS", UiTheme.Sky, enabled: true, scale))
			{
				tempoEditor.Cancel();
				StartReadingPrintedMarks(song);
			}
			return;
		}
		int shownMarks = tempoPrinted.Count(mark => mark.Source.Bpm is not null && !tempoIgnored.Contains(mark.Source.Key));
		if (DrawPanelButton(ref x, y, height, shownMarks == 0 ? "PRINTED · NONE" : $"PRINTED · {shownMarks}", UiTheme.Text,
			tempoPrintedOpen, scale))
		{
			tempoPrintedOpen = !tempoPrintedOpen;
		}
	}

	/// <summary>
	/// The marks printed in the PDF, stacked upward from <paramref name="bottom"/> above the changes.
	/// Until the user sets a tempo of their own they all play, and show PLAYING. Each has IGNORE,
	/// which hides it for good and stops it playing, and once the user's own tempo replaces them,
	/// USE, which takes one into it at its bar (the first bar's sets the start). A word without a
	/// number ("Andante") is a hint only. A row above them holds USE ALL, READ AGAIN and, once some
	/// are hidden, SHOW IGNORED.
	/// </summary>
	private static void DrawPrintedMarks(SongLoadResult song, SongPerformance performance, SongTempoMap shown,
		bool changesApply, float bottom, float height, float scale, ref SongTempoMap? edited)
	{
		List<PrintedMark> rows = tempoPrinted!.Where(mark => !tempoIgnored.Contains(mark.Source.Key)).ToList();
		int ignored = tempoPrinted!.Count - rows.Count;
		int textSize = Math.Max(10, (int)(12f * scale));
		float rowStep = height + 6f * scale;
		float left = 16f * scale;
		int visible = Math.Min(PrintedListRows, rows.Count);
		tempoPrintedScroll = Math.Clamp(tempoPrintedScroll, 0, Math.Max(0, rows.Count - visible));
		float top = bottom - 6f * scale - visible * rowStep;
		Rectangle listArea = new Rectangle(left, top, 620f * scale, visible * rowStep);
		if (rows.Count > visible && Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), listArea))
		{
			float wheel = Raylib.GetMouseWheelMove();
			if (wheel != 0)
			{
				tempoPrintedScroll = Math.Clamp(tempoPrintedScroll - Math.Sign(wheel), 0, rows.Count - visible);
			}
		}
		bool CanUse(PrintedMark mark) => mark.Usable && (mark.Measure == 0 || changesApply);
		float barLabelWidth = LabelWidth("BAR 0000", textSize) + 20f * scale;
		for (int row = 0; row < visible; row++)
		{
			PrintedMark mark = rows[tempoPrintedScroll + row];
			float x = left;
			float rowY = top + row * rowStep;
			string place = mark.Measure is int measure
				? "BAR " + SongTempoMaps.BarName(performance, measure)
				: $"PAGE {mark.Source.Page + 1}";
			DrawTempoLabel(ref x, rowY, height, barLabelWidth, place, mark.Measure is null ? UiTheme.Warning : UiTheme.Text,
				scale);
			string? words = mark.Words;
			if (mark.Tempo is not null)
			{
				DrawTempoLabel(ref x, rowY, height, 0, words is null ? null : words + "  ", UiTheme.Text, scale, mark.Tempo);
			}
			else
			{
				DrawTempoLabel(ref x, rowY, height, 0, mark.Source.Bpm is null ? $"\"{words}\" · NO NUMBER, A HINT ONLY"
					: $"\"{mark.Source.Text}\" · UNIT NOT READ", UiTheme.Muted, scale);
			}
			if (mark.Measure is null && mark.Source.Bpm is not null)
			{
				DrawTempoLabel(ref x, rowY, height, 0, "NOT IN THIS CONVERSION'S PAGES", UiTheme.Warning, scale);
			}
			SongTempoMap basis = edited ?? shown;
			// A playing mark keeps IGNORE: without a tempo of the user's, ignoring it is how a misread mark
			// stops playing.
			if (mark.Usable && TempoDetection.InUse(basis, mark))
			{
				DrawTempoLabel(ref x, rowY, height, 0, mark.Measure == 0 ? "PLAYING · START" : "PLAYING", UiTheme.Lime, scale);
			}
			else if (mark.Usable && DrawPanelAction(ref x, rowY, height, "USE", UiTheme.Lime, CanUse(mark), scale))
			{
				tempoEditor.Cancel();
				edited = TempoDetection.Use(basis, mark);
			}
			if (DrawPanelAction(ref x, rowY, height, "IGNORE", UiTheme.Warning, enabled: true, scale))
			{
				SetIgnoredPrintedMarks(song, tempoIgnored.Append(mark.Source.Key));
			}
		}

		float headerY = top - rowStep;
		float header = left;
		int numbered = tempoPrinted.Count(static mark => mark.Source.Bpm is not null);
		// A page whose staves the reader could not find was not read, which is not the same as having no mark.
		bool blind = tempoPrintedPages > 0 && tempoPrintedBlindPages == tempoPrintedPages;
		string title = blind ? "NO STAVES FOUND IN THE PDF · MARKS NOT READ"
			: tempoPrinted.Count == 0 ? "NO TEMPO MARKS FOUND IN THE PDF"
			: $"PRINTED IN THE PDF · {numbered} MARK{(numbered == 1 ? "" : "S")}" +
				(rows.Count > visible ? $" · {tempoPrintedScroll + 1}-{tempoPrintedScroll + visible} OF {rows.Count} · SCROLL" : "");
		if (!blind && tempoPrintedBlindPages > 0)
		{
			title += $" · {tempoPrintedBlindPages} PAGE{(tempoPrintedBlindPages == 1 ? "" : "S")} NOT READ";
		}
		DrawTempoLabel(ref header, headerY, height, 0, title, blind || tempoPrintedBlindPages > 0 ? UiTheme.Warning : UiTheme.Muted,
			scale);
		SongTempoMap current = edited ?? shown;
		List<PrintedMark> unused = rows.Where(mark => CanUse(mark) && !TempoDetection.InUse(current, mark)).ToList();
		if (DrawPanelAction(ref header, headerY, height, "USE ALL", UiTheme.Lime, unused.Count > 0, scale))
		{
			tempoEditor.Cancel();
			edited = unused.Aggregate(edited ?? shown, TempoDetection.Use);
		}
		if (DrawPanelAction(ref header, headerY, height, "READ AGAIN", UiTheme.Sky, tempoReading is null, scale))
		{
			tempoEditor.Cancel();
			StartReadingPrintedMarks(song);
		}
		if (ignored > 0 && DrawPanelAction(ref header, headerY, height, $"SHOW {ignored} IGNORED", UiTheme.Muted, enabled: true,
			scale))
		{
			SetIgnoredPrintedMarks(song, []);
		}
	}

	private static void SetIgnoredPrintedMarks(SongLoadResult song, IEnumerable<string> keys)
	{
		HashSet<string> kept = keys.ToHashSet(StringComparer.Ordinal);
		tempoIgnored = kept;
		if (song.Performance is SongPerformance performance)
		{
			RefreshPrintedMap(performance, song.Engine);
		}
		tempoMapsEdited = true;
		try
		{
			TempoMapStore.SetIgnoredMarks(song.SourceSha256!, kept);
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException
			or ArgumentException)
		{
			tempoStatus = "Not saved: " + error.Message;
			Console.Error.WriteLine("[TEMPO] The ignored marks were not saved: " + error.Message);
		}
	}

	/// <summary>
	/// The typed field's keys and the click that commits it, handled here rather than in a field so
	/// both still work when the row being edited has scrolled out of view.
	/// </summary>
	private static void HandleTempoTyping(SongTempoMap shown, ref SongTempoMap? edited)
	{
		if (!tempoEditor.IsEditing)
		{
			return;
		}
		if (Raylib.IsMouseButtonPressed(MouseButton.Left) &&
			!Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), tempoEditBox))
		{
			CommitTempoEditor(shown, ref edited);
			return;
		}
		int character;
		while ((character = Raylib.GetCharPressed()) > 0)
		{
			if (character <= 65535)
			{
				tempoEditor.Append((char)character);
			}
		}
		if (Raylib.IsKeyPressed(KeyboardKey.Backspace))
		{
			tempoEditor.Backspace();
		}
		if (Raylib.IsKeyPressed(KeyboardKey.Enter) || Raylib.IsKeyPressed(KeyboardKey.KpEnter))
		{
			CommitTempoEditor(shown, ref edited);
		}
		else if (Raylib.IsKeyPressed(KeyboardKey.Escape))
		{
			tempoEditor.Cancel();
		}
	}

	/// <summary>Applies the typed value to the row it was typed into.</summary>
	private static void CommitTempoEditor(SongTempoMap shown, ref SongTempoMap? edited)
	{
		int target = tempoEditor.Target;
		if (!tempoEditor.TryCommit(out double bpm))
		{
			return;
		}
		SongTempoMap basis = edited ?? shown;
		if (target < 0)
		{
			edited = basis with { Start = basis.Start with { Bpm = bpm } };
		}
		else if (target < basis.Changes.Count)
		{
			edited = basis with
			{
				Changes = basis.Changes.Select((change, at) =>
					at == target ? change with { Tempo = change.Tempo with { Bpm = bpm } } : change).ToArray()
			};
		}
	}

	/// <summary>
	/// A tempo: − and + by one BPM, a field that takes a typed value, and the beat unit, which a
	/// click moves on to the next. Returns the new tempo when a control changed it.
	/// </summary>
	private static TempoMark? DrawTempoField(ref float x, float y, float height, int target, TempoMark mark, float scale)
	{
		TempoMark? changed = null;
		float button = height;
		bool editingThis = tempoEditor.IsEditing && tempoEditor.Target == target;
		if (UiTheme.DrawButton(new Rectangle(x, y, button, height), "−", UiTheme.Muted, mark.Bpm > TempoRules.Minimum))
		{
			tempoEditor.Cancel();
			changed = mark with { Bpm = TempoRules.Step(mark.Bpm, -1) };
		}
		x += button + 4f * scale;

		Rectangle valueBox = new Rectangle(x, y, 54f * scale, height);
		Raylib.DrawRectangleRounded(valueBox, 0.16f, 8, UiTheme.Elevated);
		Color border = editingThis ? (tempoEditor.Error is not null ? UiTheme.Danger : UiTheme.Sky) : UiTheme.Border;
		Raylib.DrawRectangleRoundedLinesEx(valueBox, 0.16f, 8, Math.Max(1f, scale), border);
		// A click elsewhere has already committed any other row's typing (HandleTempoTyping).
		if (!editingThis && !tempoEditor.IsEditing && Raylib.IsMouseButtonPressed(MouseButton.Left) &&
			Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), valueBox))
		{
			tempoEditor.Begin(target, mark.Bpm);
		}
		bool typing = tempoEditor.IsEditing && tempoEditor.Target == target;
		if (typing)
		{
			tempoEditBox = valueBox;
		}
		int textSize = Math.Max(10, (int)(13f * scale));
		string text = typing ? tempoEditor.Text + "|" : TempoRules.Format(mark.Bpm);
		UiTheme.DrawText(text, (int)(valueBox.X + (valueBox.Width - UiTheme.MeasureText(text, textSize)) / 2f),
			(int)(valueBox.Y + (valueBox.Height - textSize) / 2f), textSize, UiTheme.Text);
		x += valueBox.Width + 4f * scale;

		if (UiTheme.DrawButton(new Rectangle(x, y, button, height), "+", UiTheme.Muted, mark.Bpm < TempoRules.Maximum))
		{
			tempoEditor.Cancel();
			changed = mark with { Bpm = TempoRules.Step(mark.Bpm, 1) };
		}
		x += button + 4f * scale;

		int glyphSize = Math.Max(10, (int)(14f * scale));
		Rectangle unitBox = new Rectangle(x, y, BeatUnitGlyphWidth(BeatUnit.DottedQuarter, glyphSize) + 18f * scale, height);
		bool hovered = Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), unitBox);
		Raylib.DrawRectangleRounded(unitBox, 0.5f, 10, hovered ? UiTheme.Elevated : UiTheme.Surface);
		Raylib.DrawRectangleRoundedLinesEx(unitBox, 0.5f, 10, 1, hovered ? UiTheme.Sky : UiTheme.Border);
		DrawBeatUnitGlyph(mark.Unit, unitBox.X + (unitBox.Width - BeatUnitGlyphWidth(mark.Unit, glyphSize)) / 2f,
			unitBox.Y + unitBox.Height / 2f, glyphSize, UiTheme.Text);
		if (hovered && Raylib.IsMouseButtonPressed(MouseButton.Left))
		{
			tempoEditor.Cancel();
			changed = mark with { Unit = mark.Unit.Next() };
		}
		x += unitBox.Width + 6f * scale;
		return changed;
	}

	/// <summary>
	/// An opaque, unclickable pill holding text, or with <paramref name="tempo"/> a tempo as
	/// "♩=110", so labels read over the falling notes. A width of 0 fits the content.
	/// </summary>
	private static void DrawTempoLabel(ref float x, float y, float height, float width, string? text, Color color,
		float scale, TempoMark? tempo = null)
	{
		int textSize = Math.Max(10, (int)(12f * scale));
		string after = tempo is null ? "" : "=" + TempoRules.Format(tempo.Bpm);
		float content = (text is null ? 0 : LabelWidth(text, textSize)) +
			(tempo is null ? 0 : BeatUnitGlyphWidth(tempo.Unit, textSize) + LabelWidth(after, textSize));
		Rectangle bounds = new Rectangle(x, y, width > 0 ? width : content + 20f * scale, height);
		Raylib.DrawRectangleRounded(bounds, 0.5f, 10, UiTheme.Surface);
		Raylib.DrawRectangleRoundedLinesEx(bounds, 0.5f, 10, 1, UiTheme.Border);
		float textX = bounds.X + 10f * scale;
		int textY = (int)(bounds.Y + (bounds.Height - textSize) / 2f);
		if (text is not null)
		{
			UiTheme.DrawText(text, (int)textX, textY, textSize, color);
			textX += LabelWidth(text, textSize);
		}
		if (tempo is not null)
		{
			DrawBeatUnitGlyph(tempo.Unit, textX, bounds.Y + bounds.Height / 2f, textSize, color);
			UiTheme.DrawText(after, (int)(textX + BeatUnitGlyphWidth(tempo.Unit, textSize)), textY, textSize, color);
		}
		x += bounds.Width + 6f * scale;
	}

	/// <summary>How wide <see cref="DrawBeatUnitGlyph"/> draws <paramref name="unit"/> at <paramref name="size"/>.</summary>
	private static float BeatUnitGlyphWidth(BeatUnit unit, float size)
	{
		float width = size * 0.56f;
		if (unit is BeatUnit.DottedQuarter or BeatUnit.DottedHalf)
		{
			width += size * 0.3f;
		}
		if (unit == BeatUnit.Eighth)
		{
			width += size * 0.3f;
		}
		return width + size * 0.12f;
	}

	/// <summary>
	/// A note symbol for a beat unit, drawn rather than typed because the UI font is loaded without
	/// the musical symbols. <paramref name="centerY"/> is the middle of the text line it sits in.
	/// </summary>
	private static void DrawBeatUnitGlyph(BeatUnit unit, float x, float centerY, float size, Color color)
	{
		float radiusX = size * 0.26f;
		float radiusY = size * 0.19f;
		Vector2 head = new(x + radiusX + 1f, centerY + size * 0.24f);
		if (unit is BeatUnit.Half or BeatUnit.DottedHalf)
		{
			Raylib.DrawEllipseLines((int)head.X, (int)head.Y, radiusX, radiusY, color);
			Raylib.DrawEllipseLines((int)head.X, (int)head.Y, radiusX - 1f, radiusY - 1f, color);
		}
		else
		{
			Raylib.DrawEllipse((int)head.X, (int)head.Y, radiusX, radiusY, color);
		}
		float thickness = Math.Max(1.2f, size * 0.08f);
		Vector2 stemBottom = new(head.X + radiusX - thickness / 2f, head.Y);
		Vector2 stemTop = new(stemBottom.X, head.Y - size * 0.82f);
		Raylib.DrawLineEx(stemBottom, stemTop, thickness, color);
		if (unit == BeatUnit.Eighth)
		{
			Raylib.DrawLineEx(stemTop, new Vector2(stemTop.X + size * 0.3f, stemTop.Y + size * 0.36f), thickness, color);
		}
		if (unit is BeatUnit.DottedQuarter or BeatUnit.DottedHalf)
		{
			Raylib.DrawCircleV(new Vector2(head.X + radiusX + size * 0.2f, head.Y - size * 0.04f),
				Math.Max(1.4f, size * 0.07f), color);
		}
	}
}
