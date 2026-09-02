namespace SynthesiaClone;

public enum LibraryColumn
{
    None,
    Pdf,
    Cache,
    Midi
}

/// <summary>
/// Text filters for the three landing-page columns.
///
/// Exactly one box holds focus at a time, so typed characters cannot land in two columns
/// at once. Focus also gates the landing page's single-letter shortcuts (B to browse,
/// H / O to pick an engine), which would otherwise fire while the user is typing a query
/// that happens to contain those letters.
/// </summary>
public sealed class LibrarySearchState
{
    private const int MaximumLength = 64;

    private string pdf = string.Empty;
    private string cache = string.Empty;
    private string midi = string.Empty;

    public LibraryColumn Focused { get; private set; }

    /// <summary>True while a search box owns the keyboard.</summary>
    public bool IsTyping => Focused != LibraryColumn.None;

    public void Focus(LibraryColumn column) => Focused = column;

    public void ClearFocus() => Focused = LibraryColumn.None;

    public string Get(LibraryColumn column) => column switch
    {
        LibraryColumn.Pdf => pdf,
        LibraryColumn.Cache => cache,
        LibraryColumn.Midi => midi,
        _ => string.Empty
    };

    public void Set(LibraryColumn column, string? value)
    {
        string next = value ?? string.Empty;
        if (next.Length > MaximumLength)
        {
            next = next[..MaximumLength];
        }
        switch (column)
        {
            case LibraryColumn.Pdf:
                pdf = next;
                break;
            case LibraryColumn.Cache:
                cache = next;
                break;
            case LibraryColumn.Midi:
                midi = next;
                break;
        }
    }

    public void Append(LibraryColumn column, char character)
    {
        if (!char.IsControl(character))
        {
            Set(column, Get(column) + character);
        }
    }

    public void Backspace(LibraryColumn column)
    {
        string current = Get(column);
        if (current.Length > 0)
        {
            Set(column, current[..^1]);
        }
    }

    /// <summary>
    /// Case-insensitive match where every whitespace-separated term must appear somewhere
    /// in the text. Terms rather than one substring because these are filenames: a score
    /// saved as "Honkai_Star_Rail_-_Sparkle" should be reachable by typing "rail sparkle",
    /// which a plain substring match would miss.
    /// </summary>
    public static bool Matches(string? text, string? query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return true;
        }
        if (string.IsNullOrEmpty(text))
        {
            return false;
        }
        foreach (string term in query.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!text.Contains(term, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
        }
        return true;
    }
}
