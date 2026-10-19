namespace SynthesiaClone;

internal enum OmrRecoveryAction
{
    RetrySameEngine,
    RetryWithHomr,
    ChooseAnotherFile
}

internal static class OmrRecoveryPolicy
{
    public static IReadOnlyList<OmrRecoveryAction> GetActions(OmrEngine engine) =>
        engine switch
        {
            OmrEngine.Homr =>
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.ChooseAnotherFile
            ],
            OmrEngine.Zeus or OmrEngine.Homr465 or OmrEngine.Homr480 =>
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.RetryWithHomr,
                OmrRecoveryAction.ChooseAnotherFile
            ],
            _ => throw new ArgumentOutOfRangeException(
                nameof(engine), engine, "Unknown OMR engine.")
        };

    public static string GetSameEngineLabel(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => "Retry homr",
        OmrEngine.Homr465 => "Retry HOMR 465",
        OmrEngine.Homr480 => "Retry HOMR 480",
        OmrEngine.Zeus => "Retry Zeus anyway",
        _ => throw new ArgumentOutOfRangeException(
            nameof(engine), engine, "Unknown OMR engine.")
    };

    /// <summary>
    /// The engine the error screen offers instead: HOMR 480, the default, falls back to the
    /// secondary HOMR 465; 465 and Zeus fall back to HOMR 426; 426 to Zeus.
    /// </summary>
    public static OmrEngine GetAlternateEngine(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr480 => OmrEngine.Homr465,
        OmrEngine.Zeus or OmrEngine.Homr465 => OmrEngine.Homr,
        _ => OmrEngine.Zeus
    };

    public static string GetAlternateLabel(OmrEngine engine) => GetAlternateEngine(engine) switch
    {
        OmrEngine.Homr465 => "Retry HOMR 465",
        OmrEngine.Homr => "Retry HOMR 426",
        _ => "Retry Zeus"
    };
}
