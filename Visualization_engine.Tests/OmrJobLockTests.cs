using System.Diagnostics;
using System.Text.Json;
using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class OmrJobLockTests
{
    [Fact]
    public void LockOfKilledSupervisorIsReleased()
    {
        using TemporaryDirectory jobs = new();
        string lockPath = WriteLock(jobs, ExitedProcessId());

        Assert.True(OmrPipeline.ReleaseAbandonedJobLock(jobs.Path));
        Assert.False(File.Exists(lockPath));
        Assert.Empty(Directory.GetFiles(jobs.Path, ".worker.lock*"));
        Assert.True(Directory.Exists(Path.Combine(jobs.Path, "killed")));
    }

    [Fact]
    public void ProcessThatReusedTheOwnersIdDoesNotHoldTheLock()
    {
        using TemporaryDirectory jobs = new();
        string lockPath = WriteLock(jobs, Environment.ProcessId);
        File.SetLastWriteTimeUtc(lockPath, new DateTime(2000, 1, 1, 0, 0, 0, DateTimeKind.Utc));

        Assert.True(OmrPipeline.ReleaseAbandonedJobLock(jobs.Path));
        Assert.False(File.Exists(lockPath));
    }

    [Fact]
    public void RunningSupervisorKeepsItsLock()
    {
        using TemporaryDirectory jobs = new();
        string lockPath = WriteLock(jobs, Environment.ProcessId);
        string text = File.ReadAllText(lockPath);

        Assert.False(OmrPipeline.ReleaseAbandonedJobLock(jobs.Path));
        Assert.Equal(text, File.ReadAllText(lockPath));
    }

    [Fact]
    public void LockKeptAfterTheSupervisorFinishedStays()
    {
        using TemporaryDirectory jobs = new();
        string lockPath = WriteLock(jobs, ExitedProcessId());
        File.WriteAllText(Path.Combine(jobs.Path, "killed", "result.json"), "{}");

        Assert.False(OmrPipeline.ReleaseAbandonedJobLock(jobs.Path));
        Assert.True(File.Exists(lockPath));
    }

    [Theory]
    [InlineData("existing worker")]
    [InlineData("{\"output\": \"x\"}")]
    [InlineData("")]
    public void LockWithUnknownOwnerStays(string text)
    {
        using TemporaryDirectory jobs = new();
        string lockPath = jobs.CreateFile(".worker.lock", text);

        Assert.False(OmrPipeline.ReleaseAbandonedJobLock(jobs.Path));
        Assert.Equal(text, File.ReadAllText(lockPath));
    }

    [Fact]
    public void MissingLockIsNothingToRelease()
    {
        using TemporaryDirectory jobs = new();

        Assert.False(OmrPipeline.ReleaseAbandonedJobLock(jobs.Path));
        Assert.False(OmrPipeline.ReleaseAbandonedJobLock(Path.Combine(jobs.Path, "absent")));
    }

    // The supervisor's own format: its process id and the job's receipt folder.
    private static string WriteLock(TemporaryDirectory jobs, int supervisorId)
    {
        string output = Path.Combine(jobs.Path, "killed");
        Directory.CreateDirectory(output);
        return jobs.CreateFile(".worker.lock", JsonSerializer.Serialize(
            new Dictionary<string, object> { ["supervisor_pid"] = supervisorId, ["output"] = output }));
    }

    private static int ExitedProcessId()
    {
        using Process process = Process.Start(new ProcessStartInfo("cmd.exe", "/c exit")
        {
            UseShellExecute = false,
            CreateNoWindow = true
        })!;
        process.WaitForExit();
        return process.Id;
    }
}
