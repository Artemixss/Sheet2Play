using System.Numerics;
using Raylib_cs;
using Color = Raylib_cs.Color;
using Rectangle = Raylib_cs.Rectangle;

namespace SynthesiaClone;

/// <summary>
/// The EXPRESSION panel on the playback screen: Pedal, Dynamics, Articulations and Repeats, each
/// on or off, saved in the settings and applied to the song that is playing without reloading it.
/// </summary>
internal static partial class Program
{
	/// <summary>The panel's switches as the user last set them.</summary>
	private static ExpressionOptions expression = new();

	/// <summary>The switches the playing session was built with, to map its position on a change.</summary>
	private static ExpressionOptions sessionExpression = new();

	/// <summary>Set by a switch; acted on by the main loop, which owns the audio output.</summary>
	private static bool expressionChanged;

	/// <summary>
	/// Whether the switches are showing. Closed at every start, so the playback screen opens clean;
	/// the button itself says when a switch is off.
	/// </summary>
	private static bool expressionPanelOpen;

	private static void LoadExpressionSettings()
	{
		try
		{
			expression = AppSettingsStore.LoadExpression();
		}
		catch (Exception error)
		{
			Console.Error.WriteLine("[SETTINGS] Expression switches were not read: " + error.Message);
		}
	}

	/// <summary>A playback session for a song under the panel's current switches.</summary>
	private static PlaybackSession CreateSongSession(SongLoadResult song, double audioOffsetSeconds)
	{
		SongPlayback playback = ExpressionPlayback.ForSong(song, expression);
		sessionExpression = expression;
		RebuildOverlay(song, expression, playback.Pedal);
		return new PlaybackSession(playback.Notes, audioOffsetSeconds, playback.Pedal);
	}

	/// <summary>
	/// Rebuilds the playing session after a switch, keeping its place, its speed and whether it
	/// was playing. Only Repeats moves the place, to the same point of the same measure.
	/// </summary>
	private static PlaybackController? ApplyExpressionChange(PlaybackController? playback, SongLoadResult? song,
		IMidiOutput midiOutput, AudioOutput audioOutput)
	{
		expressionChanged = false;
		if (playback is null || song is null || expression == sessionExpression)
		{
			return playback;
		}
		ExpressionOptions previous = sessionExpression;
		double position = ExpressionPlayback.MapPosition(song, previous, expression, playback.Position);
		bool wasPlaying = playback.IsPlaying;
		double rate = playback.PlaybackRate;
		double offset = playback.AudioOffsetSeconds;
		playback.Stop();
		PlaybackSession session = CreateSongSession(song, offset);
		PlaybackController rebuilt = new(session, midiOutput, audioOutput.CreateTimebase(session, offset));
		if (Math.Abs(rate - 1.0) > 1e-9)
		{
			rebuilt.SetPlaybackRate(rate);
		}
		rebuilt.Seek(position, wasPlaying);
		Console.Error.WriteLine($"[EXPRESSION] {Describe(previous)} -> {Describe(expression)} " +
			$"notes={session.Notes.Count} pedal={session.Pedal.Count} position={position:F2}");
		return rebuilt;
	}

	private static string Describe(ExpressionOptions options) =>
		$"pedal={(options.Pedal ? "on" : "off")} dynamics={(options.Dynamics ? "on" : "off")} " +
		$"articulations={(options.Articulations ? "on" : "off")} repeats={(options.Repeats ? "on" : "off")} " +
		$"auto_pedal={(options.AutoPedal ? "on" : "off")}";

	/// <summary>
	/// The EXPRESSION button, bottom-left above the Export button, and when it is open the switches
	/// to its right. A switch whose mark the song does not have says so, because HOMR reads no pedal
	/// or dynamics and the user should not hunt for them.
	/// </summary>
	private static void DrawExpressionPanel(SongLoadResult song, UiLayout layout)
	{
		float scale = layout.Scale;
		float height = 26f * scale;
		float y = (float)layout.HitLineY - 2f * height - 20f * scale;
		float x = 16f * scale;
		if (DrawExpressionButton(ref x, y, height, scale))
		{
			expressionPanelOpen = !expressionPanelOpen;
		}
		if (!expressionPanelOpen)
		{
			return;
		}

		ExpressionAvailability available = ExpressionPlayback.Availability(song);
		ExpressionOptions changed = expression;
		if (DrawExpressionSwitch(ref x, y, height, "PEDAL", expression.Pedal, available.Pedal, scale))
		{
			changed = expression with { Pedal = !expression.Pedal };
		}
		if (DrawExpressionSwitch(ref x, y, height, "DYNAMICS", expression.Dynamics, available.Dynamics, scale))
		{
			changed = expression with { Dynamics = !expression.Dynamics };
		}
		if (DrawExpressionSwitch(ref x, y, height, "ARTICULATIONS", expression.Articulations, available.Articulations, scale))
		{
			changed = expression with { Articulations = !expression.Articulations };
		}
		if (DrawExpressionSwitch(ref x, y, height, "REPEATS", expression.Repeats, available.Repeats, scale))
		{
			changed = expression with { Repeats = !expression.Repeats };
		}
		// Off by default, and not counted as OFF on the button: it adds a pedal the score does not have.
		if (DrawExpressionSwitch(ref x, y, height, "AUTO PEDAL", expression.AutoPedal, available.AutoPedal, scale))
		{
			changed = expression with { AutoPedal = !expression.AutoPedal };
		}
		if (changed != expression)
		{
			expression = changed;
			expressionChanged = true;
			try
			{
				AppSettingsStore.SaveExpression(expression);
			}
			catch (Exception error)
			{
				Console.Error.WriteLine("[SETTINGS] Expression switches were not persisted: " + error.Message);
			}
		}
	}

	/// <summary>
	/// The button that opens and closes the switches: a chevron pointing the way they will move,
	/// and how many are off, so a switched-off pedal is never hidden behind a closed panel.
	/// </summary>
	private static bool DrawExpressionButton(ref float x, float y, float height, float scale)
	{
		int off = new[] { expression.Pedal, expression.Dynamics, expression.Articulations, expression.Repeats }
			.Count(static enabled => !enabled);
		int textSize = Math.Max(10, (int)(12f * scale));
		string label = "EXPRESSION" + (off > 0 ? $" · {off} OFF" : "");
		float chevron = 6f * scale;
		Rectangle bounds = new Rectangle(x, y, (float)UiTheme.MeasureText(label, textSize) + 34f * scale, height);
		x += bounds.Width + 6f * scale;

		bool hovered = Raylib.CheckCollisionPointRec(Raylib.GetMousePosition(), bounds);
		Raylib.DrawRectangleRounded(bounds, 0.5f, 10, hovered || expressionPanelOpen ? UiTheme.Elevated : UiTheme.Surface);
		Raylib.DrawRectangleRoundedLinesEx(bounds, 0.5f, 10, 1, expressionPanelOpen ? UiTheme.Sky : UiTheme.Border);
		Color text = off > 0 ? UiTheme.Warning : UiTheme.Text;
		UiTheme.DrawText(label, (int)(bounds.X + 10f * scale), (int)(bounds.Y + (bounds.Height - textSize) / 2f),
			textSize, text);
		// Drawn rather than typed: the UI font is loaded without the arrow characters.
		float tipX = bounds.X + bounds.Width - 12f * scale;
		float middleY = bounds.Y + bounds.Height / 2f;
		float backX = expressionPanelOpen ? tipX + chevron * 0.6f : tipX - chevron * 0.6f;
		float thickness = Math.Max(1.5f, 1.6f * scale);
		Raylib.DrawLineEx(new Vector2(backX, middleY - chevron * 0.75f), new Vector2(expressionPanelOpen ? tipX - chevron * 0.6f : tipX + chevron * 0.6f, middleY), thickness, UiTheme.Muted);
		Raylib.DrawLineEx(new Vector2(backX, middleY + chevron * 0.75f), new Vector2(expressionPanelOpen ? tipX - chevron * 0.6f : tipX + chevron * 0.6f, middleY), thickness, UiTheme.Muted);
		return hovered && Raylib.IsMouseButtonPressed(MouseButton.Left);
	}

	/// <summary>One on/off pill, drawn like the TIMING FIX switch. Returns true on a click.</summary>
	private static bool DrawExpressionSwitch(ref float x, float y, float height, string name, bool enabled,
		bool available, float scale)
	{
		int textSize = Math.Max(10, (int)(12f * scale));
		string label = name + (enabled ? " ON" : " OFF") + (available ? "" : " · none");
		Rectangle bounds = new Rectangle(x, y, (float)UiTheme.MeasureText(label, textSize) + 20f * scale, height);
		x += bounds.Width + 6f * scale;

		Vector2 mouse = Raylib.GetMousePosition();
		bool hovered = Raylib.CheckCollisionPointRec(mouse, bounds);
		bool lit = enabled && available;
		Color accent = available ? UiTheme.Lime : UiTheme.Muted;
		// Opaque underneath, so the notes falling behind do not show through the lit tint.
		Raylib.DrawRectangleRounded(bounds, 0.5f, 10, hovered ? UiTheme.Elevated : UiTheme.Surface);
		if (lit)
		{
			Raylib.DrawRectangleRounded(bounds, 0.5f, 10, new Color((int)accent.R, (int)accent.G, (int)accent.B, 38));
		}
		Raylib.DrawRectangleRoundedLinesEx(bounds, 0.5f, 10, lit ? 2 : 1, lit ? accent : UiTheme.Border);
		UiTheme.DrawText(label, (int)(bounds.X + 10f * scale), (int)(bounds.Y + (bounds.Height - textSize) / 2f),
			textSize, lit ? UiTheme.Text : UiTheme.Muted);
		return hovered && Raylib.IsMouseButtonPressed(MouseButton.Left);
	}
}
