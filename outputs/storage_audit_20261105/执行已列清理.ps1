param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$audit = 'D:\rob-memory\outputs\storage_audit_20261105'
$receiptPath = Join-Path $audit 'cleanup_execution.json'
$receipt = [ordered]@{started_at=(Get-Date).ToString('o');execute=[bool]$Execute;status='verifying';deleted=@();skipped=@();protected=@();error=$null}
$archiveLocks = @()
$zipReaders = @()
$approved = @{}
$trees = @{}
function Save-Receipt { $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding utf8 }
function Read-Json($path) { Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json }
function Normalize($path) { [IO.Path]::GetFullPath($path).TrimEnd('\') }
function Assert-Path($path,$root) {
    $full = Normalize $path
    $base = Normalize $root
    if ($full -ne $base -and -not $full.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)) {throw "Path outside allowlist: $path"}
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {throw "Reparse point refused: $cursor"}
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) {break}
        $cursor = $parent.FullName
    }
    return $full
}
function Hash-Stream($stream) {
    $h=[Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($h.ComputeHash($stream)).Replace('-','').ToLowerInvariant() } finally {$h.Dispose()}
}
function File-State($path) {
    $f=Get-Item -LiteralPath $path -Force
    $stream=[IO.File]::Open($f.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {$digest=Hash-Stream $stream} finally {$stream.Dispose()}
    $after=Get-Item -LiteralPath $path -Force
    if($f.Length -ne $after.Length -or $f.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks){throw "File changed while hashing: $path"}
    [pscustomobject]@{path=$after.FullName;bytes=[int64]$after.Length;mtime_utc_ticks=$after.LastWriteTimeUtc.Ticks;sha256=$digest}
}
function Add-File($group,$path,$root,$expectedHash,$expectedBytes,[switch]$SkipChanged) {
    $full=Assert-Path $path $root
    if(-not(Test-Path -LiteralPath $full -PathType Leaf)) {throw "Listed file missing: $full"}
    $state=File-State $full
    if(($null -ne $expectedBytes -and $state.bytes -ne $expectedBytes) -or ($expectedHash -and $state.sha256 -ne $expectedHash)) {
        if($SkipChanged){$receipt.skipped+=@{group=$group;path=$full;reason='changed_since_audit'};return}
        throw "Listed file differs from audited/archived content: $full"
    }
    if($approved.ContainsKey($full)){throw "Overlapping candidate: $full"}
    $state|Add-Member -NotePropertyName group -NotePropertyValue $group
    $approved[$full]=$state
}
function Add-Tree($group,$path,$root,$expected) {
    $full=Assert-Path $path $root
    foreach($d in $script:registeredWsl) {if($d -eq $full -or $d.StartsWith($full+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Registered WSL disk lies in target: $full"}}
    $items=@(Get-ChildItem -LiteralPath $full -Recurse -Force)
    if(@($items|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw "Tree contains reparse point: $full"}
    $files=@($items|Where-Object {-not $_.PSIsContainer})
    if($files.Count -ne $expected.Count){throw "Tree file count changed: $full"}
    foreach($f in $files) {
        $relative=$f.FullName.Substring($full.Length+1).Replace('\','/')
        if(-not $expected.ContainsKey($relative)){throw "Unlisted file in tree: $($f.FullName)"}
        $e=$expected[$relative]
        $s=File-State $f.FullName
        if($s.sha256 -ne $e.sha256 -or $s.bytes -ne $e.bytes){throw "Extracted file differs from ZIP: $($f.FullName)"}
        $s|Add-Member -NotePropertyName group -NotePropertyValue $group
        $approved[$s.path]=$s
    }
    $trees[$group]=[pscustomobject]@{path=$full;root=$root;files=$files.Count;bytes=[int64](($files|Measure-Object Length -Sum).Sum)}
    Write-Output "$group verified: $($files.Count) files"
}
function Assert-UnchangedTree($tree,$group) {
    $null=Assert-Path $tree.path $tree.root
    $items=@(Get-ChildItem -LiteralPath $tree.path -Recurse -Force)
    if(@($items|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Reparse point appeared before deletion'}
    $files=@($items|Where-Object {-not $_.PSIsContainer})
    if($files.Count -ne $tree.files){throw 'Tree changed after validation'}
    foreach($f in $files){$s=$approved[$f.FullName];if($null -eq $s -or $s.group -ne $group -or $s.bytes -ne $f.Length -or $s.mtime_utc_ticks -ne $f.LastWriteTimeUtc.Ticks){throw "Tree file changed before deletion: $($f.FullName)"}}
}
try {
    Save-Receipt
    $receipt.free_bytes_before=(Get-PSDrive -Name D).Free
    $registeredWsl=@(Get-ChildItem -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'|Get-ItemProperty|ForEach-Object {Normalize ($_.BasePath -replace '^\\\\\?\\','')})
    if('D:\rob-memory\wsl\Ubuntu22.04' -notin $registeredWsl){throw 'Expected active Ubuntu registration changed'}
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archiveSpecs=@(
        @{path='D:\rob-memory-migration-20261021\rob-memory_迁移包_20261021.zip';sha='d38c199fd1e5442eac2dcd707bd8eadb45d4b50fce2273e7ab2b21a89e0ce734'},
        @{path='D:\hunter_increment_since_20261021_20261031\Hunter_增量_20261021至20261031.zip';sha='2778323963823f4a34439e81a00aa154d889f58a63498cd769800ce6ce85aa75'})
    foreach($spec in $archiveSpecs){
        $s=[IO.File]::Open($spec.path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        $archiveLocks+=,$s
        if((Hash-Stream $s) -ne $spec.sha){throw "Backup ZIP SHA mismatch: $($spec.path)"}
        $s.Position=0
        $zipReaders+=,[IO.Compression.ZipArchive]::new($s,[IO.Compression.ZipArchiveMode]::Read,$true)
        $receipt.protected+=@{path=$spec.path;sha256=$spec.sha;locked_against_write_and_delete=$true}
    }
    $manifestEntry=$zipReaders[0].GetEntry('rob-memory-migration/MANIFEST.json')
    $reader=[IO.StreamReader]::new($manifestEntry.Open(),[Text.Encoding]::UTF8)
    try{$manifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    $fullExpected=@{}
    foreach($f in $manifest.files){if(-not $f.path.StartsWith('rob-memory-migration/') -or $f.path.Contains('../')){throw 'Unexpected full ZIP path'};$fullExpected[$f.path]=@{bytes=[int64]$f.bytes;sha256=$f.sha256}}
    $ms=$manifestEntry.Open()
    try{$mh=Hash-Stream $ms}finally{$ms.Dispose()}
    $fullExpected['rob-memory-migration/MANIFEST.json']=@{bytes=[int64]$manifestEntry.Length;sha256=$mh}
    Add-Tree 'A1' 'D:\rob-memory-migration-20261021\desktop-restore\payload' 'D:\rob-memory-migration-20261021\desktop-restore' $fullExpected
    $deltaExpected=@{}
    foreach($e in $zipReaders[1].Entries){
        if($e.FullName.EndsWith('/')){continue}
        $prefix='Hunter_increment_20261021_to_20261031/'
        if(-not $e.FullName.StartsWith($prefix) -or $e.FullName.Contains('../')){throw 'Unexpected increment ZIP path'}
        $s=$e.Open();try{$h=Hash-Stream $s}finally{$s.Dispose()}
        $deltaExpected[$e.FullName.Substring($prefix.Length)]=@{bytes=[int64]$e.Length;sha256=$h}
    }
    Add-Tree 'A3' 'D:\hunter_increment_since_20261021_20261031\Hunter_increment_20261021_to_20261031' 'D:\hunter_increment_since_20261021_20261031' $deltaExpected
    Add-File 'A2' 'D:\rob-memory-migration-20261021\desktop-restore\wsl.3.0.3.0.x64.msi' 'D:\rob-memory-migration-20261021\desktop-restore' $null 367575040
    $cacheRoots=@('D:\rob-memory\outputs\hunter_nav2_append_20261027\.build','D:\rob-memory\outputs\weekly_mapping_ppt_20261014\.build','D:\rob-memory\outputs\hunter_nav2_refined_20261028\build','D:\rob-memory\outputs\group_meeting_20261020\.build')
    $slides=@(Read-Json (Join-Path $audit 'presentation_cache_candidates.json'))
    if($slides.Count -ne 93){throw 'B1 list count changed'}
    foreach($f in $slides){$matches=@($cacheRoots|Where-Object {(Normalize $f.path).StartsWith($_+'\',[StringComparison]::OrdinalIgnoreCase)});if($matches.Count -ne 1 -or [IO.Path]::GetExtension($f.path) -notin @('.png','.pptx')){throw "B1 path outside cache whitelist: $($f.path)"};Add-File 'B1' $f.path $matches[0] $f.sha256 $f.bytes}
    $python=@(Read-Json (Join-Path $audit 'regenerable_python_cache_candidates.json'))
    if($python.Count -ne 133){throw 'B2 list count changed'}
    foreach($f in $python){
        $source=$f.path -replace '\\__pycache__\\([^\\]+)\.cpython-[^\\]+\.pyc$','\$1.py'
        if($source -eq $f.path -or (Normalize $source) -ne (Normalize $f.source_path) -or -not(Test-Path -LiteralPath $source -PathType Leaf)){throw "B2 source missing/invalid: $($f.path)"}
        Add-File 'B2' $f.path 'D:\rob-memory' $f.sha256 $f.bytes -SkipChanged
    }
    $maps=@(Read-Json (Join-Path $audit 'historical_map_backup_verification.json'))
    if($maps.Count -ne 12){throw 'C1 list count changed'}
    $pcdRoot='D:\rob-memory\knowledge_base\Hunter知识库\算法实现\fast_lio2_完整源码\spark_fast_lio\PCD'
    foreach($f in $maps){
        $p=Normalize $f.path
        if($p -ne 'D:\rob-memory\knowledge_base\Hunter知识库\配置文件\地图文件\all_raw_points.pcd' -and $p -notmatch ('^'+[regex]::Escape($pcdRoot)+'\\scans_(?:[1-9]|10|11)\.pcd$')){throw "C1 path outside exact whitelist: $p"}
        $archiveKey='rob-memory-migration/rob-memory/'+$p.Substring('D:\rob-memory\'.Length).Replace('\','/')
        if(-not $fullExpected.ContainsKey($archiveKey) -or $fullExpected[$archiveKey].sha256 -ne $f.sha256){throw 'C1 backup identity mismatch'}
        Add-File 'C1' $p 'D:\rob-memory\knowledge_base' $f.sha256 $f.bytes
    }
    $receipt.validated_files=$approved.Count
    $receipt.validated_bytes=[int64](($approved.Values|Measure-Object bytes -Sum).Sum)
    $receipt.status='validated'
    Save-Receipt
    Write-Output "Validated $($receipt.validated_files) exact files; execute=$Execute"
    if($Execute){
        $receipt.status='deleting';Save-Receipt
        foreach($group in @('A1','A3')){
            $t=$trees[$group]
            Assert-UnchangedTree $t $group
            Remove-Item -LiteralPath $t.path -Recurse -Force
            if(Test-Path -LiteralPath $t.path){throw "Directory deletion incomplete: $($t.path)"}
            $receipt.deleted+=@{group=$group;path=$t.path;files=$t.files;bytes=$t.bytes}
            Save-Receipt;Write-Output "$group removed: $($t.files) files"
        }
        foreach($group in @('A2','B1','B2','C1')){
            foreach($s in @($approved.Values|Where-Object {$_.group -eq $group}|Sort-Object path)){
                $f=Get-Item -LiteralPath $s.path -Force
                if($f.Length -ne $s.bytes -or $f.LastWriteTimeUtc.Ticks -ne $s.mtime_utc_ticks){$receipt.skipped+=@{group=$group;path=$s.path;reason='changed_after_verification'};continue}
                $null=Assert-Path $s.path (Split-Path -Parent $s.path)
                Remove-Item -LiteralPath $s.path -Force
                $receipt.deleted+=@{group=$group;path=$s.path;files=1;bytes=$s.bytes;sha256=$s.sha256}
            }
            Save-Receipt;Write-Output "$group listed files removed"
        }
        if(-not(Test-Path -LiteralPath 'D:\rob-memory\wsl\Ubuntu22.04\ext4.vhdx')){throw 'Active disk disappeared'}
        foreach($spec in $archiveSpecs){if(-not(Test-Path -LiteralPath $spec.path)){throw 'Protected ZIP disappeared'}}
        $receipt.status='complete'
    }
} catch {
    $receipt.status='failed'
    $receipt.error=$_.Exception.Message
    throw
} finally {
    foreach($z in $zipReaders){$z.Dispose()}
    foreach($s in $archiveLocks){$s.Dispose()}
    $receipt.finished_at=(Get-Date).ToString('o')
    $receipt.deleted_files=[int64](($receipt.deleted|Measure-Object files -Sum).Sum)
    $receipt.deleted_bytes=[int64](($receipt.deleted|Measure-Object bytes -Sum).Sum)
    $receipt.free_bytes_after=(Get-PSDrive -Name D).Free
    Save-Receipt
    Write-Output ([pscustomobject]@{status=$receipt.status;deleted_files=$receipt.deleted_files;deleted_bytes=$receipt.deleted_bytes;skipped=@($receipt.skipped).Count;receipt=$receiptPath}|ConvertTo-Json -Compress)
}
