using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

public static class AppSettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };

    public static OmrEngine LoadEngine()
    {
        return LoadEngineFromPath(GetSettingsPath());
    }

    internal static OmrEngine LoadEngineFromPath(string settingsPath)
    {
        if (!File.Exists(settingsPath))
        {
            return RepairLegacySettings(settingsPath);
        }

        try
        {
            AppSettings? settings = JsonSerializer.Deserialize<AppSettings>(
                File.ReadAllText(settingsPath),
                JsonOptions);
            return settings is not null && Enum.IsDefined(settings.OmrEngine)
                ? settings.OmrEngine
                : RepairLegacySettings(settingsPath);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine(
                $"[SETTINGS] Could not read {settingsPath}; using homr. {exception.Message}");
            return RepairLegacySettings(settingsPath);
        }
    }

    public static void SaveEngine(OmrEngine engine)
    {
        SaveEngineToPath(engine, GetSettingsPath());
    }

    internal static void SaveEngineToPath(OmrEngine engine, string settingsPath)
    {
        if (!Enum.IsDefined(engine))
        {
            throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.");
        }

        string directory = Path.GetDirectoryName(settingsPath)
            ?? throw new InvalidOperationException("Settings path has no parent directory.");
        Directory.CreateDirectory(directory);
        string temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileName(settingsPath)}.{Guid.NewGuid():N}.tmp");
        try
        {
            string json = JsonSerializer.Serialize(new AppSettings(engine), JsonOptions);
            File.WriteAllText(temporaryPath, json);
            File.Move(temporaryPath, settingsPath, overwrite: true);
        }
        finally
        {
            try
            {
                if (File.Exists(temporaryPath))
                {
                    File.Delete(temporaryPath);
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    public static string GetSettingsPath()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        if (string.IsNullOrWhiteSpace(localApplicationData))
        {
            throw new InvalidOperationException(
                "Windows LocalApplicationData directory is unavailable.");
        }
        return Path.Combine(localApplicationData, "Sheet2Play", "settings.json");
    }

    private static OmrEngine RepairLegacySettings(string settingsPath)
    {
        try
        {
            SaveEngineToPath(OmrEngine.Homr, settingsPath);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"[SETTINGS] Could not rewrite legacy settings: {exception.Message}");
        }
        return OmrEngine.Homr;
    }

    private sealed record AppSettings(OmrEngine OmrEngine);
}
