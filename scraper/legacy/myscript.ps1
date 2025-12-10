# Assuming $process is the System.Diagnostics.Process object for your started process
$process = Get-Process -Id 

# Check if the process has standard output redirection
if ($process.StartInfo.RedirectStandardOutput) {
    # Read the standard output content
    $outputContent = $process.StandardOutput.ReadToEnd()

    # Display the output
    Write-Output "Standard Output:"
    Write-Output $outputContent
} else {
    Write-Output "Standard output redirection is not enabled for the process."
}
