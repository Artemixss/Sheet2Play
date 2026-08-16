using System.Globalization;

namespace SynthesiaClone;

public static class PlaybackRateRules
{
    public const double Minimum = 0.05;
    public const double Maximum = 2.00;
    public const double StepSize = 0.05;
    public const double Default = 1.00;

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
        decimal stepped = Math.Round(
            (decimal)current + direction * (decimal)StepSize,
            2,
            MidpointRounding.AwayFromZero);
        return (double)Math.Clamp(stepped, (decimal)Minimum, (decimal)Maximum);
    }

    public static bool TryParse(string text, out double rate, out string? error)
    {
        rate = Default;
        error = null;
        if (string.IsNullOrWhiteSpace(text))
        {
            error = "Enter a speed.";
            return false;
        }

        string candidate = text.Trim();
        if (candidate.EndsWith('x') || candidate.EndsWith('X'))
        {
            candidate = candidate[..^1].TrimEnd();
        }
        int dot = candidate.IndexOf('.');
        int comma = candidate.IndexOf(',');
        if (dot >= 0 && comma >= 0)
        {
            error = "Use one decimal separator.";
            return false;
        }
        int separator = Math.Max(dot, comma);
        if (separator >= 0 && candidate.Length - separator - 1 > 2)
        {
            error = "Use at most two decimals.";
            return false;
        }
        string normalized = candidate.Replace(',', '.');
        if (!decimal.TryParse(
                normalized,
                NumberStyles.AllowDecimalPoint,
                CultureInfo.InvariantCulture,
                out decimal parsed))
        {
            error = "Enter a number.";
            return false;
        }
        if (parsed < (decimal)Minimum || parsed > (decimal)Maximum)
        {
            error = $"Use {Minimum:0.00}x–{Maximum:0.00}x.";
            return false;
        }
        rate = (double)parsed;
        return true;
    }
}

internal sealed class PlaybackRateEditor
{
    private double previousRate = PlaybackRateRules.Default;

    public bool IsEditing { get; private set; }
    public string Text { get; private set; } = string.Empty;
    public string? Error { get; private set; }

    public void Begin(double rate)
    {
        previousRate = rate;
        Text = rate.ToString("0.00", CultureInfo.InvariantCulture);
        Error = null;
        IsEditing = true;
    }

    public void Append(char character)
    {
        if (!IsEditing || Text.Length >= 7 ||
            !(char.IsAsciiDigit(character) || character is '.' or ','))
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

    public bool TryCommit(out double rate)
    {
        if (!IsEditing)
        {
            rate = previousRate;
            return false;
        }
        if (!PlaybackRateRules.TryParse(Text, out rate, out string? error))
        {
            Error = error;
            return false;
        }
        IsEditing = false;
        previousRate = rate;
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
