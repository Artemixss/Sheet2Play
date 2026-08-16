using Raylib_cs;
using Color = Raylib_cs.Color;
using Font = Raylib_cs.Font;
using Rectangle = Raylib_cs.Rectangle;

namespace SynthesiaClone;

public readonly record struct UiLayout(
    int Width,
    int Height,
    float Scale,
    int HeaderHeight,
    int KeyboardHeight,
    int HitLineY,
    double FallSpeed,
    Rectangle Content)
{
    public static UiLayout Create(int width, int height)
    {
        width = Math.Max(960, width);
        height = Math.Max(540, height);
        float scale = Math.Clamp(Math.Min(width / 1280f, height / 720f), 0.75f, 2f);
        int headerHeight = Math.Clamp((int)Math.Round(92 * scale), 72, 150);
        int keyboardHeight = Math.Clamp(
            (int)Math.Round(150 * scale),
            110,
            Math.Max(110, (int)(height * 0.27)));
        int hitLineY = height - keyboardHeight;
        float margin = Math.Clamp(32 * scale, 24, 64);
        return new UiLayout(
            width,
            height,
            scale,
            headerHeight,
            keyboardHeight,
            hitLineY,
            200 * scale,
            new Rectangle(margin, headerHeight, width - margin * 2, hitLineY - headerHeight));
    }
}

public static class UiTheme
{
    private static Font regularFont;
    private static Font semiboldFont;
    private static bool customFontsLoaded;

    public static readonly Color Background = new(11, 15, 20, 255);
    public static readonly Color Surface = new(21, 27, 35, 255);
    public static readonly Color Elevated = new(29, 38, 50, 255);
    public static readonly Color Border = new(53, 66, 82, 255);
    public static readonly Color Text = new(238, 243, 248, 255);
    public static readonly Color Muted = new(145, 160, 179, 255);
    public static readonly Color Sky = new(88, 191, 246, 255);
    public static readonly Color Lime = new(117, 220, 121, 255);
    public static readonly Color Danger = new(239, 100, 97, 255);
    public static readonly Color Warning = new(246, 190, 76, 255);

    public static void InitializeFonts()
    {
        string fontDirectory = Path.Combine(AppContext.BaseDirectory, "assets", "fonts");
        string regularPath = Path.Combine(fontDirectory, "Inter-Regular.ttf");
        string semiboldPath = Path.Combine(fontDirectory, "Inter-SemiBold.ttf");
        try
        {
            int[] codepoints = Enumerable.Range(32, 0x0250 - 32)
                .Concat([0x2026, 0x2212])
                .Distinct()
                .ToArray();
            regularFont = Raylib.LoadFontEx(regularPath, 48, codepoints, codepoints.Length);
            semiboldFont = Raylib.LoadFontEx(semiboldPath, 48, codepoints, codepoints.Length);
            customFontsLoaded = Raylib.IsFontValid(regularFont) && Raylib.IsFontValid(semiboldFont);
            if (customFontsLoaded)
            {
                Raylib.SetTextureFilter(regularFont.Texture, TextureFilter.Bilinear);
                Raylib.SetTextureFilter(semiboldFont.Texture, TextureFilter.Bilinear);
            }
            else
            {
                Console.Error.WriteLine("[UI] Inter font assets are invalid; using Raylib's default font.");
            }
        }
        catch (Exception exception)
        {
            customFontsLoaded = false;
            Console.Error.WriteLine($"[UI] Inter fonts could not be loaded; using default font. {exception.Message}");
        }
    }

    public static void ShutdownFonts()
    {
        if (!customFontsLoaded)
        {
            return;
        }
        Raylib.UnloadFont(regularFont);
        Raylib.UnloadFont(semiboldFont);
        customFontsLoaded = false;
    }

    public static void DrawText(string text, int x, int y, int fontSize, Color color)
    {
        if (!customFontsLoaded)
        {
            Raylib.DrawText(text, x, y, fontSize, color);
            return;
        }
        Font font = fontSize >= 20 ? semiboldFont : regularFont;
        Raylib.DrawTextEx(font, text, new System.Numerics.Vector2(x, y), fontSize, 0, color);
    }

    public static int MeasureText(string text, int fontSize)
    {
        if (!customFontsLoaded)
        {
            return Raylib.MeasureText(text, fontSize);
        }
        Font font = fontSize >= 20 ? semiboldFont : regularFont;
        return (int)Math.Ceiling(Raylib.MeasureTextEx(font, text, fontSize, 0).X);
    }

    public static void DrawCard(Rectangle bounds, float scale = 1)
    {
        Raylib.DrawRectangleRounded(bounds, 0.08f, 12, Surface);
        Raylib.DrawRectangleRoundedLinesEx(bounds, 0.08f, 12, Math.Max(1, scale), Border);
    }

    public static bool DrawButton(
        Rectangle bounds,
        string label,
        Color accent,
        bool enabled = true,
        bool selected = false)
    {
        System.Numerics.Vector2 mouse = Raylib.GetMousePosition();
        bool hovered = enabled && Raylib.CheckCollisionPointRec(mouse, bounds);
        Color fill = !enabled
            ? new Color((int)Elevated.R, Elevated.G, Elevated.B, 130)
            : selected
                ? accent
                : hovered
                    ? new Color(
                        Math.Min(255, Elevated.R + 16),
                        Math.Min(255, Elevated.G + 16),
                        Math.Min(255, Elevated.B + 16),
                        255)
                    : Elevated;
        Raylib.DrawRectangleRounded(bounds, 0.16f, 10, fill);
        Raylib.DrawRectangleRoundedLinesEx(bounds, 0.16f, 10, 1.5f, selected ? accent : Border);
        int fontSize = Math.Max(14, (int)(18 * Math.Min(1.4f, bounds.Height / 44f)));
        int textWidth = MeasureText(label, fontSize);
        Color textColor = enabled ? Text : Muted;
        DrawText(
            label,
            (int)(bounds.X + (bounds.Width - textWidth) / 2),
            (int)(bounds.Y + (bounds.Height - fontSize) / 2),
            fontSize,
            textColor);
        return hovered && Raylib.IsMouseButtonPressed(MouseButton.Left);
    }

    public static void DrawBadge(Rectangle bounds, string label, Color accent)
    {
        Raylib.DrawRectangleRounded(bounds, 0.5f, 10, new Color((int)accent.R, accent.G, accent.B, 45));
        Raylib.DrawRectangleRoundedLinesEx(bounds, 0.5f, 10, 1, accent);
        int fontSize = Math.Max(12, (int)(bounds.Height * 0.48f));
        int width = MeasureText(label, fontSize);
        DrawText(
            label,
            (int)(bounds.X + (bounds.Width - width) / 2),
            (int)(bounds.Y + (bounds.Height - fontSize) / 2),
            fontSize,
            accent);
    }

    public static void DrawProgressBar(
        Rectangle bounds,
        double fraction,
        bool animated,
        double animationSeconds)
    {
        fraction = Math.Clamp(fraction, 0, 1);
        Raylib.DrawRectangleRounded(bounds, 0.5f, 10, Elevated);
        float filledWidth = (float)(bounds.Width * fraction);
        if (filledWidth > 1)
        {
            Rectangle fill = new(bounds.X, bounds.Y, filledWidth, bounds.Height);
            Raylib.DrawRectangleRounded(fill, 0.5f, 10, Sky);
        }
        if (animated && filledWidth < bounds.Width)
        {
            float pulseWidth = Math.Min(90, bounds.Width * 0.18f);
            float available = Math.Max(1, bounds.Width - filledWidth - pulseWidth);
            float offset = (float)((animationSeconds * 90) % (available + pulseWidth)) - pulseWidth;
            Rectangle pulse = new(
                bounds.X + filledWidth + Math.Max(0, offset),
                bounds.Y,
                Math.Min(pulseWidth, bounds.Width - filledWidth),
                bounds.Height);
            if (pulse.Width > 0)
            {
                Raylib.DrawRectangleRounded(pulse, 0.5f, 8, new Color((int)Sky.R, Sky.G, Sky.B, 75));
            }
        }
        Raylib.DrawRectangleRoundedLinesEx(bounds, 0.5f, 10, 1, Border);
    }

    public static string Ellipsize(string text, int fontSize, int maximumWidth)
    {
        if (MeasureText(text, fontSize) <= maximumWidth)
        {
            return text;
        }
        const string suffix = "...";
        int suffixWidth = MeasureText(suffix, fontSize);
        int length = text.Length;
        while (length > 0 &&
               MeasureText(text[..length], fontSize) + suffixWidth > maximumWidth)
        {
            length--;
        }
        return length == 0 ? suffix : text[..length] + suffix;
    }
}
