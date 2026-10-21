using System.Diagnostics;
using System.Text.Json;

namespace SynthesiaClone;

/// <summary>
/// <c>--detect-tempo PDF STORE_DIRECTORY [PERFORMANCE]</c>: reads a PDF's printed tempo marks the way
/// READ PRINTED MARKS does, through the bridge's <c>tempo_marks.py</c> in the HOMR runtime, and
/// prints them as JSON. STORE_DIRECTORY stands in for the library, so the user's own store is not
/// touched. With a <c>performance.json</c> of a conversion of the PDF, it also prints the bar each
/// mark lands on in that song, as the TEMPO panel lists it.
/// </summary>
internal static partial class Program
{
	/// <summary>
	/// <c>--read-printed-tempo</c>: reads the printed tempo marks of every PDF in the library that has
	/// none for the bridge's reader yet, into the library's store, so every converted song plays at its
	/// printed tempo without opening the TEMPO panel. Already read PDFs are skipped, so it can be run
	/// again after new PDFs arrive or the reader changes. Prints one JSON line per PDF and a summary.
	/// </summary>
	private static int RunPrintedTempoLibrary()
	{
		string library = SongCache.ApplicationDirectory;
		string bridge = OmrPipeline.DefaultBridgeDirectory;
		if (TempoDetection.ReaderSha256(bridge) is not string reader)
		{
			Console.Error.WriteLine($"[TEMPO] The tempo reader ({TempoDetection.ScriptName}) is missing from {bridge}.");
			return 1;
		}
		int read = 0, kept = 0, failed = 0, withMarks = 0;
		foreach (PdfLibraryEntry entry in SongCache.GetPdfLibrary())
		{
			string source = SongCache.Sha256OfFile(entry.FullPath);
			if (TempoDetection.Load(library, source, reader) is not null)
			{
				kept++;
				continue;
			}
			Stopwatch clock = Stopwatch.StartNew();
			try
			{
				DetectedTempos detected = TempoDetection.Detect(library, bridge, entry.FullPath, source, progress: null,
					background: false);
				read++;
				int marks = detected.Marks.Count(static mark => mark.Bpm is not null);
				withMarks += marks > 0 ? 1 : 0;
				Console.WriteLine(JsonSerializer.Serialize(new
				{
					source_sha256 = source, pages = detected.Pages.Count, marks,
					pages_without_staves = detected.Pages.Count(static page => page.Systems == 0),
					seconds = Math.Round(clock.Elapsed.TotalSeconds, 1)
				}));
			}
			catch (Exception exception) when (exception is TempoDetectionException or IOException or UnauthorizedAccessException)
			{
				failed++;
				Console.WriteLine(JsonSerializer.Serialize(new { source_sha256 = source, error = exception.Message }));
			}
		}
		Console.WriteLine(JsonSerializer.Serialize(new { reader_sha256 = reader, read, already_read = kept, failed,
			read_with_numbered_marks = withMarks }));
		return failed == 0 ? 0 : 1;
	}

	private static int RunTempoDetectionVerification(string[] arguments)
	{
		try
		{
			if (arguments.Length is not (3 or 4))
			{
				throw new ArgumentException("Expected a PDF, a store directory and optionally a performance.json.");
			}
			string pdf = Path.GetFullPath(arguments[1]);
			string store = Path.GetFullPath(arguments[2]);
			string source = SongCache.Sha256OfFile(pdf);
			Stopwatch clock = Stopwatch.StartNew();
			DetectedTempos detected = TempoDetection.Detect(store, OmrPipeline.DefaultBridgeDirectory, pdf, source,
				new Progress<(int Page, int Pages)>(static step => Console.Error.WriteLine($"[TEMPO] page {step.Page} of {step.Pages}")),
				background: false);
			SongPerformance? performance = arguments.Length == 4 ? SongPerformance.Parse(File.ReadAllText(arguments[3])) : null;
			IReadOnlyList<PrintedMark>? placed = performance is null ? null : TempoDetection.Place(detected, performance);
			Console.WriteLine(JsonSerializer.Serialize(new
			{
				reader_sha256 = detected.ReaderSha256,
				source_sha256 = detected.SourceSha256,
				seconds = Math.Round(clock.Elapsed.TotalSeconds, 2),
				pages = detected.Pages.Count,
				marks = detected.Marks.Select(static mark => new { mark.Page, mark.PageMeasure, mark.Bpm, mark.Unit, mark.Text }),
				placed = placed?.Select(mark => new
				{
					bar = mark.Measure is int measure ? SongTempoMaps.BarName(performance!, measure) : null,
					bpm = mark.Tempo?.Bpm,
					unit = mark.Tempo?.Unit.ToString(),
					words = mark.Words,
					usable = mark.Usable
				})
			}, new JsonSerializerOptions { WriteIndented = true }));
			return 0;
		}
		catch (Exception exception) when (exception is ArgumentException or IOException or UnauthorizedAccessException
			or JsonException or InvalidDataException or TempoDetectionException)
		{
			Console.Error.WriteLine("[TEMPO] " + exception.Message);
			return 1;
		}
	}
}
