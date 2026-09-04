using System.Globalization;

namespace SynthesiaClone;

/// <summary>
/// Stepping and parsing for the audio offset, mirroring <see cref="PlaybackRateRules"/>.
///
/// Bounds are taken from <see cref="AppSettingsStore"/> rather than restated here, so the
/// field cannot accept a value that the settings file would silently clamp on the next save.
/// </summary>
public static class AudioOffsetRules
{
    /// <summary>
    /// Nudge size for the buttons and the [ / ] keys. Small enough to home in on a value,
    /// which does mean a single press is below the roughly 20-40ms at which a listener can
    /// notice an audio-visual shift - hence the typed field for larger jumps.
    /// </summary>
    public const int StepMilliseconds = 5;

    public static int Step(int currentMilliseconds, int direction)
    {
        if (direction is not -1 and not 1)
        {
            throw new ArgumentOutOfRangeException(nameof(direction));
        }
        return AppSettingsStore.Clamp(currentMilliseconds + (direction * StepMilliseconds));
    }

    public static bool TryParse(string text, out int milliseconds, out string? error)
    {
        milliseconds = AppSettingsStore.DefaultAudioOffsetMilliseconds;
        error = null;
        if (string.IsNullOrWhiteSpace(text))
        {
            error = "Enter a value.";
            return false;
        }

        string candidate = text.Trim();
        if (candidate.EndsWith("ms", StringComparison.OrdinalIgnoreCase))
        {
            candidate = candidate[..^2].TrimEnd();
        }
        if (!int.TryParse(candidate, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed))
        {
            error = "Whole milliseconds only.";
            return false;
        }
        if (parsed < AppSettingsStore.MinimumAudioOffsetMilliseconds ||
            parsed > AppSettingsStore.MaximumAudioOffsetMilliseconds)
        {
            error = $"Use {AppSettingsStore.MinimumAudioOffsetMilliseconds}" +
                $"-{AppSettingsStore.MaximumAudioOffsetMilliseconds} ms.";
            return false;
        }

        milliseconds = parsed;
        return true;
    }
}

internal sealed class AudioOffsetEditor
{
    public bool IsEditing { get; private set; }
    public string Text { get; private set; } = string.Empty;
    public string? Error { get; private set; }

    public void Begin(int milliseconds)
    {
        Text = milliseconds.ToString(CultureInfo.InvariantCulture);
        Error = null;
        IsEditing = true;
    }

    public void Append(char character)
    {
        if (!IsEditing || Text.Length >= 3 || !char.IsAsciiDigit(character))
        {
            return;
        }
        Text += character;
        Error = null;
    }

    public void Backspace()
    {
        if (!IsEditing || Text.Length == 0)
        {
            return;
        }
        Text = Text[..^1];
        Error = null;
    }

    public bool TryCommit(out int milliseconds)
    {
        if (!IsEditing)
        {
            milliseconds = AppSettingsStore.DefaultAudioOffsetMilliseconds;
            return false;
        }
        if (!AudioOffsetRules.TryParse(Text, out milliseconds, out string? error))
        {
            Error = error;
            return false;
        }
        IsEditing = false;
        Text = string.Empty;
        Error = null;
        return true;
    }

    public void Cancel()
    {
        IsEditing = false;
        Text = string.Empty;
        Error = null;
    }
}
