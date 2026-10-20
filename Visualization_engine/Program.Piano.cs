using System.Diagnostics;

namespace SynthesiaClone;

/// <summary>
/// <c>--build-piano-bank</c>: the step of <c>scripts\install-piano.ps1</c> that needs the app's own
/// code, converting an SFZ piano's samples into the bank the SFZ engine plays from.
/// </summary>
internal static partial class Program
{
	private static int RunBuildPianoBank(string[] args)
	{
		if (args.Length < 3)
		{
			Console.Error.WriteLine("[PIANO] Usage: --build-piano-bank <instrument.sfz> <output folder>");
			return 1;
		}
		string sfz = Path.GetFullPath(args[1]);
		string directory = Path.GetFullPath(args[2]);
		if (!File.Exists(sfz))
		{
			Console.Error.WriteLine("[PIANO] Instrument not found: " + sfz);
			return 1;
		}
		try
		{
			Stopwatch elapsed = Stopwatch.StartNew();
			BankIndex index = PianoLibrary.BuildBank(sfz, directory);
			long bytes = new FileInfo(Path.Combine(directory, SfzBank.BankName)).Length;
			Console.WriteLine($"[PIANO] {index.Samples.Count} samples, {bytes / 1024.0 / 1024.0:0} MB bank, " +
				$"{elapsed.Elapsed.TotalSeconds:0.0} s: {directory}");
			return 0;
		}
		catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidDataException)
		{
			Console.Error.WriteLine("[PIANO] Could not build the bank: " + error.Message);
			return 1;
		}
	}
}
