"""Create the single-branch direct-XML revision repair in an isolated frontend profile."""
from pathlib import Path

from homr_465_common import write_new
from screening_homr_compatibility import sha256_file


def main() -> None:
    here = Path(__file__).resolve().parent
    workspace = here.parents[1]
    source = workspace / "Visualization_engine/OmrPipeline.cs"
    destination = here / "probes/homr465-frontend-profile/OmrPipeline.cs"
    original = source.read_text(encoding="utf-8")
    before = "public static string GetEngineRevision(OmrEngine engine) => engine switch\n    {\n        OmrEngine.Homr => HomrEngineRevision,\n        OmrEngine.Zeus => ZeusEngineRevision,"
    after = before + '\n        OmrEngine.MusicXml => "direct-xml",'
    if original.count(before) != 1:
        raise ValueError("Expected unique, reviewed revision switch")
    if destination.exists():
        raise FileExistsError(destination)
    destination.write_text(original.replace(before, after), encoding="utf-8")
    write_new(here / "reports/homr-timing-465/phase3/runtime-repair.json", {
        "profile": "isolated-direct-xml-revision-v1", "source": str(source),
        "source_sha256": sha256_file(source), "copy": str(destination),
        "copy_sha256": sha256_file(destination), "added_branch": 'OmrEngine.MusicXml => "direct-xml",',
        "changes_scored_outputs": False, "production_modified": False,
        "scope": "Explicit installed Python + published Bridge direct-XML validation only; no candidate inference launcher or production adoption"})
    print("Created isolated direct-XML revision branch; production untouched")


if __name__ == "__main__":
    main()
