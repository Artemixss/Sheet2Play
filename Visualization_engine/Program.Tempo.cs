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

	private static int tempoListScroll;

	/// <summary>Why the last edit was not saved, shown in the panel until the next edit.</summary>
	private static string? tempoStatus;

	private static readonly TempoEditor tempoEditor = new();

	/// <summary>Where the field being typed into was drawn last frame, so a click elsewhere commits it.</summary>
	private static Rectangle tempoEditBox;

	/// <summary>The tempo <paramref name="song"/> plays at under its stored map; null plays its score.</summary>
	private static TempoOverride? TempoFor(SongLoadResult song)
	{
		LoadTempoMap(song);
		return SongTempoMaps.Override(tempoMap, song.Performance);
	}

	/// <summary>The stored tempo for a song, read fresh, for the bench and offline render.</summary>
	internal static TempoOverride? StoredTempo(SongLoadResult song)
	{
		if (song.SourceSha256 is not string source || song.Performance is null)
		{
			return null;
		}
		try
		{
			return SongTempoMaps.Override(TempoMapStore.Get(source), song.Performance);
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
		Console.Error.WriteLine($"[TEMPO] {song.DisplayName}: {(map is null ? "reset to the score" : DescribeMap(map))}");
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
	/// says the start tempo, and in the warning colour when the song is on the 120 fallback, so a
	/// song that has no real tempo yet is never hidden behind a closed panel.
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
		SongTempoMap shown = tempoMap ?? tempoScoreMap!;
		bool changesApply = SongTempoMaps.ChangesApply(shown, performance);
		bool fallback = tempoMap is null && performance.Tempos.All(static tempo => tempo.QuarterBpm is null);
		int changeCount = changesApply ? shown.Changes.Count : 0;
		string suffix = fallback
			? " · DEFAULT"
			: !changesApply
				? " · CHECK BARS"
				: changeCount > 0 ? $" · {changeCount} CHANGE{(changeCount == 1 ? "" : "S")}" : "";
		if (DrawPanelButton(ref x, y, height, "TEMPO  ", fallback || !changesApply ? UiTheme.Warning : UiTheme.Text,
			tempoPanelOpen, scale, shown.Start.Unit, "=" + TempoRules.Format(shown.Start.Bpm) + suffix))
		{
			tempoPanelOpen = !tempoPanelOpen;
			tempoEditor.Cancel();
		}
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
		int barIndex = songOverlay.BarIndexAt(position);
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

		DrawTempoChanges(song, performance, shown, changesApply, y, height, scale, ref edited);

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
	/// the warning colour with KEEP (they are right for this one too) and CLEAR.
	/// </summary>
	private static void DrawTempoChanges(SongLoadResult song, SongPerformance performance, SongTempoMap shown,
		bool changesApply, float y, float height, float scale, ref SongTempoMap? edited)
	{
		int count = shown.Changes.Count;
		if (count == 0)
		{
			return;
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
