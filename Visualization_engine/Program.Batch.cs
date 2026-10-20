using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace SynthesiaClone;

/// <summary>
/// <c>--convert-batch LIST JOURNAL [--engine homr480] [--no-timing-fix]</c>: converts the library files
/// named in LIST, one at a time, through the same <see cref="SongCache.LoadOrCreateDetailed"/> path
/// the app uses, so each song lands in the cache playlist exactly as if it had been opened.
/// </summary>
/// <remarks>
/// For a chosen set of songs, where <c>--reconvert</c> takes the whole library and the migration
/// runner writes HOMR 465 MIDI caches. LIST holds one path per line, relative to <c>songs/pdf</c>
/// or absolute. JOURNAL gets one JSON line per attempt; a rerun skips every file already converted
/// with the same content, so a stopped batch resumes where it left off. Recognition runs in the
/// pipeline's own supervised worker; between songs the batch also stops, resumable, when memory or
/// the system commit reserve runs low, rather than starting another heavy run.
/// </remarks>
internal static partial class Program
{
	private const double BatchMemoryStopPercent = 85;
	private const long BatchCommitReserveBytes = 4L * 1024 * 1024 * 1024;

	private static int RunConvertBatch(string[] args)
	{
		if (args.Length < 3)
		{
			Console.Error.WriteLine("[BATCH] Usage: --convert-batch LIST JOURNAL [--engine homr480] [--no-timing-fix]");
			return 1;
		}
		string listPath = Path.GetFullPath(args[1]);
		string journalPath = Path.GetFullPath(args[2]);
		OmrEngine engine = OmrEngine.Homr480;
		if (GetDemoOption(args, "--engine") is string named &&
			!Enum.TryParse(named.Replace("homr", "Homr", StringComparison.OrdinalIgnoreCase), ignoreCase: true, out engine))
		{
			Console.Error.WriteLine("[BATCH] Unknown engine: " + named);
			return 1;
		}
		bool timing = !args.Contains("--no-timing-fix");
		string library = Path.Combine(SongCache.ApplicationDirectory, "songs", "pdf");
		string[] items = File.ReadAllLines(listPath)
			.Select(static line => line.Trim())
			.Where(static line => line.Length > 0 && !line.StartsWith('#'))
			.Select(line => Path.IsPathFullyQualified(line) ? line : Path.Combine(library, line))
			.ToArray();
		HashSet<string> done = ReadBatchDone(journalPath);
		Directory.CreateDirectory(Path.GetDirectoryName(journalPath)!);
		Console.WriteLine($"[BATCH] {items.Length} file(s) with {OmrPipeline.GetEngineName(engine)}, timing fix " +
			$"{(timing ? "on" : "off")}; {done.Count} already done; journal {journalPath}");

		int converted = 0;
		int failed = 0;
		for (int index = 0; index < items.Length; index++)
		{
			string source = items[index];
			string label = $"[BATCH] {index + 1}/{items.Length} {Path.GetFileNameWithoutExtension(source)}";
			if (!File.Exists(source))
			{
				failed++;
				AppendBatch(journalPath, new { file = source, status = "missing" });
				Console.WriteLine($"{label}: MISSING");
				continue;
			}
			string hash = SongCache.Sha256OfFile(source);
			if (done.Contains(BatchKey(hash, engine, timing)))
			{
				Console.WriteLine($"{label}: already done");
				continue;
			}
			if (BatchMemoryProblem() is string pressure)
			{
				AppendBatch(journalPath, new { file = source, status = "stopped", reason = pressure });
				Console.WriteLine($"[BATCH] STOPPED before {Path.GetFileName(source)}: {pressure}. Rerun to resume.");
				return 2;
			}
			Stopwatch elapsed = Stopwatch.StartNew();
			try
			{
				SongLoadResult result = SongCache.LoadOrCreateDetailed(source, engine, recordRecent: false,
					timingCorrection: timing);
				bool packaged = result.Performance is not null;
				converted++;
				AppendBatch(journalPath, new
				{
					file = source,
					source_sha256 = hash,
					engine = OmrPipeline.GetEngineName(engine),
					timing_correction = timing,
					status = packaged ? "ok" : "no_package",
					notes = result.NoteCount,
					from_cache = result.LoadedFromCache,
					manifest = result.ManifestRelativePath,
					seconds = Math.Round(elapsed.Elapsed.TotalSeconds, 1)
				});
				Console.WriteLine($"{label}: {(packaged ? "OK" : "NO PACKAGE")}, {result.NoteCount:N0} notes, " +
					$"{elapsed.Elapsed.TotalSeconds:0} s{(result.LoadedFromCache ? " (already stored)" : "")}");
			}
			catch (Exception error)
			{
				failed++;
				string code = (error as OmrPipelineException)?.ErrorCode ?? error.GetType().Name;
				AppendBatch(journalPath, new
				{
					file = source,
					source_sha256 = hash,
					engine = OmrPipeline.GetEngineName(engine),
					timing_correction = timing,
					status = "failed",
					error = code,
					message = error.Message,
					seconds = Math.Round(elapsed.Elapsed.TotalSeconds, 1)
				});
				Console.WriteLine($"{label}: FAILED {code}: {error.Message}");
			}
		}
		Console.WriteLine($"[BATCH] done: {converted} converted, {failed} failed or missing");
		return failed == 0 ? 0 : 1;
	}

	private static string BatchKey(string hash, OmrEngine engine, bool timing) =>
		$"{hash}|{OmrPipeline.GetEngineName(engine)}|{timing}";

	/// <summary>The files a journal records as converted, so a rerun skips them.</summary>
	private static HashSet<string> ReadBatchDone(string journalPath)
	{
		HashSet<string> done = [];
		if (!File.Exists(journalPath))
		{
			return done;
		}
		foreach (string line in File.ReadAllLines(journalPath))
		{
			try
			{
				using JsonDocument entry = JsonDocument.Parse(line);
				JsonElement root = entry.RootElement;
				if (root.TryGetProperty("status", out JsonElement status) && status.GetString() == "ok" &&
					root.TryGetProperty("source_sha256", out JsonElement hash) &&
					root.TryGetProperty("engine", out JsonElement engine) &&
					root.TryGetProperty("timing_correction", out JsonElement timing) &&
					Enum.TryParse(engine.GetString()!.Replace("homr", "Homr", StringComparison.OrdinalIgnoreCase),
						ignoreCase: true, out OmrEngine parsed))
				{
					done.Add(BatchKey(hash.GetString()!, parsed, timing.GetBoolean()));
				}
			}
			catch (JsonException)
			{
				// A line cut off by an interruption: that file is simply attempted again.
			}
		}
		return done;
	}

	private static void AppendBatch(string journalPath, object entry) =>
		File.AppendAllText(journalPath, JsonSerializer.Serialize(entry) + Environment.NewLine);

	/// <summary>Why another conversion should not start now, or null when memory allows it.</summary>
	private static string? BatchMemoryProblem()
	{
		MemoryStatus status = new() { Length = (uint)Marshal.SizeOf<MemoryStatus>() };
		if (!GlobalMemoryStatusEx(ref status))
		{
			return null;
		}
		if (status.MemoryLoad >= BatchMemoryStopPercent)
		{
			return $"RAM {status.MemoryLoad}% used";
		}
		if ((long)status.AvailablePageFile < BatchCommitReserveBytes)
		{
			return $"only {status.AvailablePageFile / 1024.0 / 1024 / 1024:0.0} GiB of commit left";
		}
		double commitUsed = 100.0 * (status.TotalPageFile - status.AvailablePageFile) / Math.Max(1, status.TotalPageFile);
		return commitUsed >= BatchMemoryStopPercent ? $"commit {commitUsed:0}% used" : null;
	}

	[StructLayout(LayoutKind.Sequential)]
	private struct MemoryStatus
	{
		public uint Length;
		public uint MemoryLoad;
		public ulong TotalPhysical;
		public ulong AvailablePhysical;
		public ulong TotalPageFile;
		public ulong AvailablePageFile;
		public ulong TotalVirtual;
		public ulong AvailableVirtual;
		public ulong AvailableExtendedVirtual;
	}

	[DllImport("kernel32.dll", SetLastError = true)]
	[return: MarshalAs(UnmanagedType.Bool)]
	private static extern bool GlobalMemoryStatusEx(ref MemoryStatus status);
}
