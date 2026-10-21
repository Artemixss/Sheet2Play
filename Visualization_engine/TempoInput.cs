using System.Globalization;

namespace SynthesiaClone;

/// <summary>Stepping and parsing for the TEMPO panel's BPM fields, mirroring <see cref="PlaybackRateRules"/>.</summary>
public static class TempoRules
{
    /// <summary>Beats per minute of the chosen unit, wide enough for a slow ♩. or a fast ♪.</summary>
    public const double Minimum = 10;
    public const double Maximum = 400;
    public const double StepSize = 1;

    public static bool IsInRange(double bpm) => double.IsFinite(bpm) && bpm >= Minimum && bpm <= Maximum;

    /// <summary>One step up or down, landing on a whole number so 110.5 steps to 111 or 110.</summary>
    public static double Step(double current, int direction)
    {
        if (!double.IsFinite(current))
        {
            throw new ArgumentOutOfRangeException(nameof(current));
        }
        if (direction is not -1 and not 1)
        {
            throw new ArgumentOutOfRangeException(nameof(direction));
        }
        double stepped = direction > 0 ? Math.Floor(current + StepSize) : Math.Ceiling(current - StepSize);
        return Math.Clamp(stepped, Minimum, Maximum);
    }

    public static bool TryParse(string text, out double bpm, out string? error)
    {
        bpm = 0;
        error = null;
        if (string.IsNullOrWhiteSpace(text))
        {
            error = "Enter a tempo.";
            return false;
        }
        string candidate = text.Trim();
        if (candidate.EndsWith("bpm", StringComparison.OrdinalIgnoreCase))
        {
            candidate = candidate[..^3].TrimEnd();
        }
        int dot = candidate.IndexOf('.');
        int comma = candidate.IndexOf(',');
        if (dot >= 0 && comma >= 0)
        {
            error = "Use one decimal separator.";
            return false;
        }
        int separator = Math.Max(dot, comma);
        if (separator >= 0 && candidate.Length - separator - 1 > 1)
        {
            error = "Use at most one decimal.";
            return false;
        }
        if (!decimal.TryParse(candidate.Replace(',', '.'), NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture,
                out decimal parsed))
        {
            error = "Enter a number.";
            return false;
        }
        if (!IsInRange((double)parsed))
        {
            error = $"Use {Minimum:0}-{Maximum:0}.";
            return false;
        }
        bpm = (double)parsed;
        return true;
    }

    /// <summary>"110", or "110.5" for a tempo with a fraction.</summary>
    public static string Format(double bpm) => bpm.ToString("0.#", CultureInfo.InvariantCulture);
}

/// <summary>
/// The TEMPO panel's typed field. One editor serves every row; <see cref="Target"/> says which
/// row it is editing: -1 for the start tempo, otherwise the index of a change.
/// </summary>
internal sealed class TempoEditor
{
    public bool IsEditing { get; private set; }
    public int Target { get; private set; }
    public string Text { get; private set; } = string.Empty;
    public string? Error { get; private set; }

    public void Begin(int target, double bpm)
    {
        Target = target;
        Text = TempoRules.Format(bpm);
        Error = null;
        IsEditing = true;
    }

    public void Append(char character)
    {
        if (!IsEditing || Text.Length >= 6 || !(char.IsAsciiDigit(character) || character is '.' or ','))
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

    public bool TryCommit(out double bpm)
    {
        if (!IsEditing)
        {
            bpm = 0;
            return false;
        }
        if (!TempoRules.TryParse(Text, out bpm, out string? error))
        {
            Error = error;
            return false;
        }
        Cancel();
        return true;
    }

    public void Cancel()
    {
        IsEditing = false;
        Text = string.Empty;
        Error = null;
    }
}
