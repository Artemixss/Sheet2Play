using Raylib_cs;
using Color = Raylib_cs.Color;
using Rectangle = Raylib_cs.Rectangle;

namespace SynthesiaClone;

/// <summary>
/// The playback screen's view of the score (<c>plans/2026-10-19-musicxml-songs.md</c>, Phase 5): bar
/// lines, the pedal lane, the song badges, and the EXPORT panel's MIDI, MusicXML and Re-convert
/// actions beside MP3.
/// </summary>
internal static partial class Program
{
	/// <summary>Bars and pedal of the playing session. Rebuilt whenever the session is.</summary>
	private static SongOverlay songOverlay = SongOverlay.Empty;

	/// <summary>The engine the home screen has selected, which Re-convert converts with.</summary>
	private static OmrEngine reconvertEngine = OmrEngine.Homr480;

	/// <summary>Set by Re-convert; performed by the main loop, which owns the load queue.</summary>
	private static bool reconvertRequested;

	private enum SongExport
	{
		Midi,
		MusicXml
	}

	/// <summary>Set by an export button; performed by the main loop, which owns the session.</summary>
	private static SongExport? songExportRequested;

	/// <summary>Whether the playing song has a score file, looked up once per song rather than every frame.</summary>
	private static (SongLoadResult? Song, bool HasScore) scoreLookup;

	private static bool HasScore(SongLoadResult song)
	{
		if (!ReferenceEquals(scoreLookup.Song, song))
		{
			scoreLookup = (song, SongCache.ScorePath(song) is not null);
		}
		return scoreLookup.HasScore;
	}

	/// <summary>Widths of the fixed labels this screen draws, measured once per size rather than every frame.</summary>
	private static readonly Dictionary<(string Text, int Size), int> labelWidths = [];

	private static int LabelWidth(string text, int size)
	{
		if (!labelWidths.TryGetValue((text, size), out int width))
		{
			width = UiTheme.MeasureText(text, size);
			labelWidths[(text, size)] = width;
		}
		return width;
	}

	/// <summary>The overlay for a session built from <paramref name="song"/> under <paramref name="options"/>.</summary>
	private static void RebuildOverlay(SongLoadResult song, ExpressionOptions options, IReadOnlyList<PedalChange> pedal)
	{
		songOverlay = SongOverlay.For(song.Performance, SongTimelineOptions.For(options), pedal);
	}

	/// <summary>
	/// One faint line across the note field where each bar starts. Drawn before the notes, so a note
	/// always reads on top of a line. No numbers: the user kept the lines and asked for the text to go.
	/// </summary>
	/// <remarks>
	/// Placed with the same arithmetic as <see cref="DrawFallingNote"/>'s callers, so a bar line meets
	/// the hit line on the same frame as the bar's first note. Only bars inside the visible window are
	/// visited, found by binary search, so a long song costs no more than a short one.
	/// </remarks>
	private static void DrawBarLines(double position, UiLayout layout)
	{
		SongOverlay overlay = songOverlay;
		if (overlay.Bars.Count == 0)
		{
			return;
		}
		double topSeconds = position + (double)(layout.HitLineY - layout.HeaderHeight) / layout.FallSpeed;
		Color line = new Color((int)UiTheme.Border.R, (int)UiTheme.Border.G, (int)UiTheme.Border.B, 170);
		for (int index = overlay.FirstBarFrom(position); index < overlay.Bars.Count; index++)
		{
			OverlayBar bar = overlay.Bars[index];
			if (bar.Seconds > topSeconds)
			{
				break;
			}
			int y = layout.HitLineY - (int)Math.Floor((bar.Seconds - position) * layout.FallSpeed);
			Raylib.DrawLine(0, y, layout.Width, y, line);
		}
	}

	/// <summary>
	/// A narrow lane down the left edge where the pedal's down spans fall with the notes, so a press
	/// and a release are seen coming; the foot of the lane is lit while the pedal is down.
	/// </summary>
	private static void DrawPedalLane(double position, UiLayout layout)
	{
		SongOverlay overlay = songOverlay;
		if (overlay.PedalDown.Count == 0)
		{
			return;
		}
		float scale = layout.Scale;
		int x = Math.Max(2, (int)(3f * scale));
		int width = Math.Max(4, (int)(6f * scale));
		double topSeconds = position + (double)(layout.HitLineY - layout.HeaderHeight) / layout.FallSpeed;
		Color span = new Color((int)UiTheme.Warning.R, (int)UiTheme.Warning.G, (int)UiTheme.Warning.B, 110);
		Raylib.DrawRectangle(x, layout.HeaderHeight, width, layout.HitLineY - layout.HeaderHeight,
			new Color((int)UiTheme.Border.R, (int)UiTheme.Border.G, (int)UiTheme.Border.B, 60));
		for (int index = overlay.FirstPedalFrom(position); index < overlay.PedalDown.Count; index++)
		{
			(double start, double end) = overlay.PedalDown[index];
			if (start > topSeconds)
			{
				break;
			}
			int bottomY = layout.HitLineY - (int)Math.Floor((Math.Max(start, position) - position) * layout.FallSpeed);
			int topY = end >= topSeconds
				? layout.HeaderHeight
				: layout.HitLineY - (int)Math.Floor((end - position) * layout.FallSpeed);
			Raylib.DrawRectangle(x, topY, width, Math.Max(1, bottomY - topY), span);
			if (start >= position)
			{
				// The press itself, a solid edge, so two spans that touch still read as two presses.
				Raylib.DrawRectangle(x, bottomY - 2, width, 2, UiTheme.Warning);
			}
		}
		if (overlay.IsPedalDown(position))
		{
			Raylib.DrawRectangle(x, layout.HitLineY - width * 2, width, width * 2, UiTheme.Warning);
		}
	}

	/// <summary>The facts line as last fitted, rebuilt only when the song, session or width changes.</summary>
	private static (SongLoadResult? Song, PlaybackSession? Session, int Width, string Text) songFacts;

	private static void DrawSongFacts(PlaybackController playback, SongLoadResult song, UiLayout layout)
	{
		float scale = layout.Scale;
		float x = 106f * scale;
		float right = (float)layout.Width / 2f - 104f * scale;
		float badgeHeight = 18f * scale;
		float y = 44f * scale;
		int badgeSize = Math.Max(10, (int)(11f * scale));
		void Badge(string label, Color accent)
		{
			float width = (float)LabelWidth(label, badgeSize) + 14f * scale;
			Raylib.DrawRectangleRounded(new Rectangle(x, y, width, badgeHeight), 0.5f, 10,
				new Color((int)accent.R, (int)accent.G, (int)accent.B, 40));
			Raylib.DrawRectangleRoundedLinesEx(new Rectangle(x, y, width, badgeHeight), 0.5f, 10, 1, accent);
			UiTheme.DrawText(label, (int)(x + 7f * scale), (int)(y + (badgeHeight - badgeSize) / 2f), badgeSize, accent);
			x += width + 6f * scale;
		}
		if (song.Performance is null && OmrEngines.RunsOmr(song.Engine))
		{
			Badge("MIDI (LEGACY)", UiTheme.Warning);
		}
		if (song.Performance?.TimingCorrection == true)
		{
			Badge("TIMING FIX", UiTheme.Sky);
		}
		int factsSize = Math.Max(11, (int)(13f * scale));
		int width = (int)Math.Max(0f, right - x);
		if (!ReferenceEquals(songFacts.Song, song) || !ReferenceEquals(songFacts.Session, playback.Session) ||
			songFacts.Width != width)
		{
			string facts = $"{playback.Session.Notes.Count:N0} notes";
			if (song.Performance is SongPerformance performance)
			{
				facts += " · " + performance.FeatureSummary();
			}
			songFacts = (song, playback.Session, width, UiTheme.Ellipsize(facts, factsSize, width));
		}
		UiTheme.DrawText(songFacts.Text, (int)x, (int)(46f * scale), factsSize, UiTheme.Muted);
	}

	/// <summary>
	/// Whether the EXPORT panel's actions are showing. Closed at every start, like EXPRESSION, so
	/// the playback screen opens with two small buttons rather than a row of large ones.
	/// </summary>
	private static bool exportPanelOpen;

	/// <summary>
	/// The EXPORT panel's actions, right of its button: MP3, MIDI, MusicXML, then Re-convert set a
	/// little apart because it replaces the song rather than writing a copy. An action the song
	/// cannot use is shown disabled rather than hidden, so the row does not shift between songs.
	/// </summary>
	private static void DrawSongActions(SongLoadResult song, ref float x, float y, float height, float scale)
	{
		if (DrawPanelAction(ref x, y, height, exportRunning ? "MP3 · RENDERING" : "MP3", UiTheme.Lime,
			!exportRunning, scale))
		{
			exportRequested = true;
		}
		if (DrawPanelAction(ref x, y, height, "MIDI", UiTheme.Lime, enabled: true, scale))
		{
			songExportRequested = SongExport.Midi;
		}
		if (DrawPanelAction(ref x, y, height, "MUSICXML", UiTheme.Lime, HasScore(song), scale))
		{
			songExportRequested = SongExport.MusicXml;
		}
		x += 8f * scale;
		if (DrawPanelAction(ref x, y, height, reconvertEngine == OmrEngine.Homr465 ? "RE-CONVERT · 465" : "RE-CONVERT · 480",
			UiTheme.Warning, OmrEngines.RunsOmr(song.Engine), scale))
		{
			reconvertRequested = true;
		}
	}

	/// <summary>
	/// One action pill, the size of an EXPRESSION switch. It does something rather than holding a
	/// state, so its label carries the accent and its outline lights only under the mouse.
	/// Returns true on a click.
	/// </summary>
	private static bool DrawPanelAction(ref float x, float y, float height, string label, Color accent, bool enabled,
		float scale)
	{
		int textSize = Math.Max(10, (int)(12f * scale));
		Rectangle bounds = new Rectangle(x, y, (float)LabelWidth(label, textSize) + 20f * scale, height);
		x += bounds.Width + 6f * scale;

		bool hovered = enabled && Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), bounds);
		// Opaque, so the notes falling behind do not show through.
		Raylib.DrawRectangleRounded(bounds, 0.5f, 10, hovered ? UiTheme.Elevated : UiTheme.Surface);
		Raylib.DrawRectangleRoundedLinesEx(bounds, 0.5f, 10, 1, hovered ? accent : UiTheme.Border);
		UiTheme.DrawText(label, (int)(bounds.X + 10f * scale), (int)(bounds.Y + (bounds.Height - textSize) / 2f),
			textSize, enabled ? accent : UiTheme.Muted);
		return hovered && Raylib.IsMouseButtonPressed(MouseButton.Left);
	}

	/// <summary>Writes the playing song as MIDI or copies its MusicXML into the exports folder.</summary>
	private static void ExportSong(SongExport kind, SongLoadResult? song, PlaybackController? playback)
	{
		if (song is null || playback is null)
		{
			exportStatus = "Nothing loaded to export.";
			return;
		}
		try
		{
			string safeName = string.Join("_", song.DisplayName.Split(Path.GetInvalidFileNameChars()));
			string target;
			if (kind == SongExport.Midi)
			{
				// The session the user is hearing, so the file has the same expression and repeats.
				target = Path.Combine(ExportDirectory, safeName + ".mid");
				SongCache.ExportMidi(target, playback.Session.Notes, playback.Session.Pedal);
			}
			else
			{
				target = Path.Combine(ExportDirectory, safeName + ".musicxml");
				SongCache.ExportMusicXml(song, target);
			}
			exportStatus = "Saved to " + target;
			Console.WriteLine("[EXPORT] " + target);
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException)
		{
			exportStatus = "Export failed: " + error.Message;
			Console.Error.WriteLine("[EXPORT] " + error);
		}
	}

	/// <summary>
	/// The load that re-runs recognition on the playing song's source with the selected engine, or
	/// null, with the reason in the status line, when the source is no longer in the library.
	/// </summary>
	private static LoadRequest? CreateReconvertRequest(SongLoadResult? song)
	{
		if (song is null || !OmrEngines.RunsOmr(song.Engine))
		{
			return null;
		}
		string? source = SongCache.FindSource(song);
		if (source is null)
		{
			exportStatus = "Cannot re-convert: the source file is no longer in the library.";
			return null;
		}
		Console.WriteLine($"[RECONVERT] {source} with {OmrPipeline.GetEngineName(reconvertEngine)}");
		// Forced, so an existing conversion with this engine is replaced rather than reused, and past
		// failures are not remembered against an engine that may now read it.
		return new LoadRequest(source, reconvertEngine, BypassKnownFailure: true, null, ForceReprocess: true,
			ReuseConfirmed: true);
	}
}
