#requires -Version 5.1
<#
.SYNOPSIS
Applies validated exact-text replacements without temporary files.

.DESCRIPTION
Reads one JSON patch specification from the pipeline, resolves every relative
path beneath the selected repository root, validates every replacement and
expected occurrence count in memory, and writes only after the complete batch
passes validation. Each replacement and resulting SHA-256 hash is reported.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string] $Specification,
    [Parameter()]
    [string] $Root = (Get-Location).Path,
    [Parameter()]
    [switch] $Check
)

begin {
    [Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
    $specificationBuffer = [Text.StringBuilder]::new()
}

process {
    if ($Specification) {
        [void] $specificationBuffer.AppendLine($Specification)
    }
}

end {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'

    function Resolve-PatchPath {
        param(
            [Parameter(Mandatory = $true)] [string] $RepositoryRoot,
            [Parameter(Mandatory = $true)] [string] $RelativePath,
            [switch] $AllowMissing
        )
        if ([IO.Path]::IsPathRooted($RelativePath)) {
            throw "Patch paths must be relative: $RelativePath"
        }
        $normalizedRoot = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
        $candidate = [IO.Path]::GetFullPath([IO.Path]::Combine($normalizedRoot, $RelativePath))
        $requiredPrefix = $normalizedRoot + [IO.Path]::DirectorySeparatorChar
        if (-not $candidate.StartsWith($requiredPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Patch path escapes the repository root: $RelativePath"
        }
        if (-not $AllowMissing -and -not [IO.File]::Exists($candidate)) {
            throw "Patch target does not exist: $RelativePath"
        }
        return $candidate
    }

    function Get-ExactOccurrenceCount {
        param(
            [Parameter(Mandatory = $true)] [string] $Content,
            [Parameter(Mandatory = $true)] [string] $Anchor
        )
        if ($Anchor.Length -eq 0) {
            throw 'Replacement anchors must not be empty.'
        }
        return [regex]::Matches($Content, [regex]::Escape($Anchor)).Count
    }

    if ($specificationBuffer.Length -eq 0) {
        [void] $specificationBuffer.Append([Console]::In.ReadToEnd())
    }
    $rawSpecification = $specificationBuffer.ToString().Trim()
    if (-not $rawSpecification) {
        throw 'A JSON patch specification is required on the pipeline.'
    }
    $patch = $rawSpecification | ConvertFrom-Json
    $propertyNames = @($patch.PSObject.Properties.Name)
    $edits = if ($propertyNames -contains 'edits') { @($patch.edits) } else { @() }
    $creates = if ($propertyNames -contains 'creates') { @($patch.creates) } else { @() }
    if (@($edits).Count -eq 0 -and @($creates).Count -eq 0) {
        throw 'The patch specification must contain at least one edit or create.'
    }

    $plannedFiles = [Collections.Generic.List[object]]::new()
    $plannedPaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($create in $creates) {
        $relativePath = [string] $create.path
        $absolutePath = Resolve-PatchPath -RepositoryRoot $Root -RelativePath $relativePath -AllowMissing
        if ([IO.File]::Exists($absolutePath)) {
            throw "Create target already exists: $relativePath"
        }
        if (-not [IO.Directory]::Exists([IO.Path]::GetDirectoryName($absolutePath))) {
            throw "Create target parent directory does not exist: $relativePath"
        }
        if (-not $plannedPaths.Add($absolutePath)) {
            throw "Duplicate patch target: $relativePath"
        }
        $plannedFiles.Add([pscustomobject]@{
            relativePath = $relativePath
            absolutePath = $absolutePath
            updatedContent = [string] $create.content
            replacements = [Collections.Generic.List[object]]::new()
            operation = 'create'
        })
    }
    foreach ($edit in $edits) {
        $relativePath = [string] $edit.path
        $absolutePath = Resolve-PatchPath -RepositoryRoot $Root -RelativePath $relativePath
        if (-not $plannedPaths.Add($absolutePath)) {
            throw "Duplicate patch target: $relativePath"
        }
        $originalContent = [IO.File]::ReadAllText($absolutePath)
        $updatedContent = $originalContent
        $replacementReports = [Collections.Generic.List[object]]::new()
        if (-not $edit.replacements -or $edit.replacements.Count -eq 0) {
            throw "No replacements declared for: $relativePath"
        }
        foreach ($replacement in $edit.replacements) {
            $oldText = [string] $replacement.old
            $newText = [string] $replacement.new
            $expectedOccurrences = if ($null -eq $replacement.expectedOccurrences) { 1 } else { [int] $replacement.expectedOccurrences }
            if ($expectedOccurrences -lt 1) {
                throw "expectedOccurrences must be positive for: $relativePath"
            }
            $actualOccurrences = Get-ExactOccurrenceCount -Content $updatedContent -Anchor $oldText
            if ($actualOccurrences -ne $expectedOccurrences) {
                throw "Anchor count mismatch in ${relativePath}: expected $expectedOccurrences, found $actualOccurrences."
            }
            $updatedContent = $updatedContent.Replace($oldText, $newText)
            $replacementReports.Add([pscustomobject]@{ old = $oldText; new = $newText; occurrences = $actualOccurrences })
        }
        $plannedFiles.Add([pscustomobject]@{
            relativePath = $relativePath
            absolutePath = $absolutePath
            updatedContent = $updatedContent
            replacements = $replacementReports
            operation = 'edit'
        })
    }

    foreach ($plannedFile in $plannedFiles) {
        $marker = if ($plannedFile.operation -eq 'create') { '+++' } else { '---' }
        Write-Output "$marker $($plannedFile.relativePath)"
        if ($plannedFile.operation -eq 'create') {
            Write-Output "@@ create $([Text.Encoding]::UTF8.GetByteCount($plannedFile.updatedContent)) byte(s) @@"
        }
        foreach ($replacement in $plannedFile.replacements) {
            Write-Output "@@ exact replacement x$($replacement.occurrences) @@"
            Write-Output "- $($replacement.old)"
            Write-Output "+ $($replacement.new)"
        }
    }
    if ($Check) {
        Write-Output "CHECK PASSED: $($plannedFiles.Count) file(s) validated; no files written."
        return
    }
    foreach ($plannedFile in $plannedFiles) {
        [IO.File]::WriteAllText($plannedFile.absolutePath, $plannedFile.updatedContent, [Text.UTF8Encoding]::new($false))
        $sha256 = [Security.Cryptography.SHA256]::Create()
        try {
            $stream = [IO.File]::OpenRead($plannedFile.absolutePath)
            try {
                $hashBytes = $sha256.ComputeHash($stream)
            } finally {
                $stream.Dispose()
            }
            $hash = ([BitConverter]::ToString($hashBytes)).Replace('-', '')
        } finally {
            $sha256.Dispose()
        }
        Write-Output "WROTE $($plannedFile.relativePath) SHA256=$hash"
    }
    $createCount = @($plannedFiles | Where-Object operation -eq 'create').Count
    $editCount = @($plannedFiles | Where-Object operation -eq 'edit').Count
    Write-Output "PATCH APPLIED: $($plannedFiles.Count) file(s) ($createCount created, $editCount edited), no temporary artifacts."
}