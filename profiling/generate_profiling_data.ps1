param([String]$rootDir)

# activate conda
(& "C:\Users\chsta\Miniconda3\Scripts\conda.exe" "shell.powershell" "hook") | Out-String | Invoke-Expression

conda activate daquiri

function GenerateProfilingData($inputFile) {
    pyinstrument --show-all -r html -o "./results/$($inputFile).html" $inputFile
}

Set-Location $rootDir
Get-ChildItem '.' -Filter *.py |

Foreach-Object {
    if (-NOT ($_.Name -eq "profile_all.py")) {
        Write-Output "Profiling" $_.Name
        GenerateProfilingData($_.Name)
    }
}