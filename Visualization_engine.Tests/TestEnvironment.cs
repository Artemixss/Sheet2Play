using System.Runtime.CompilerServices;

namespace Visualization_engine.Tests;

internal static class TestEnvironment
{
    // Settings and the recent-songs store resolve beside SHEET2PLAY_SETTINGS_PATH. Without it,
    // tests read and write the user's real %LOCALAPPDATA%\Sheet2Play files.
    [ModuleInitializer]
    internal static void IsolateUserState()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"sheet2play-test-state-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        Environment.SetEnvironmentVariable("SHEET2PLAY_SETTINGS_PATH", Path.Combine(directory, "settings.json"));
        AppDomain.CurrentDomain.ProcessExit += (_, _) =>
        {
            try
            {
                Directory.Delete(directory, recursive: true);
            }
            catch (Exception exception) when (
                exception is IOException or UnauthorizedAccessException)
            {
            }
        };
    }
}
