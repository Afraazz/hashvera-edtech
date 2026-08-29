param(
    [string]$OutputPath = "HashVera_Project_Presentation_15_Slides.pptx"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path ".").Path
$outFile = Join-Path $root $OutputPath
$build = Join-Path $root ("scratch\pptx_build_" + [guid]::NewGuid().ToString("N"))

function Ensure-Dir($path) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

function Write-Utf8($path, $content) {
    $dir = Split-Path -Parent $path
    if ($dir) { Ensure-Dir $dir }
    [System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))
}

function Xml-Escape([string]$value) {
    if ($null -eq $value) { return "" }
    return [System.Security.SecurityElement]::Escape($value)
}

function E([double]$inches) {
    return [int][math]::Round($inches * 914400)
}

function Text-Run([string]$text, [int]$size, [string]$color = "FFFFFF", [bool]$bold = $false) {
    $b = if ($bold) { " b=`"1`"" } else { "" }
    return "<a:r><a:rPr lang=`"en-US`" sz=`"$($size * 100)`"$b><a:solidFill><a:srgbClr val=`"$color`"/></a:solidFill><a:latin typeface=`"Aptos`"/></a:rPr><a:t>$(Xml-Escape $text)</a:t></a:r>"
}

function Text-Shape(
    [int]$id,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [string[]]$lines,
    [int]$size = 24,
    [string]$color = "FFFFFF",
    [bool]$bold = $false,
    [string]$align = "l"
) {
    $paragraphs = foreach ($line in $lines) {
        $b = if ($bold) { " b=`"1`"" } else { "" }
        "<a:p><a:pPr algn=`"$align`"/><a:r><a:rPr lang=`"en-US`" sz=`"$($size * 100)`"$b><a:solidFill><a:srgbClr val=`"$color`"/></a:solidFill><a:latin typeface=`"Aptos`"/></a:rPr><a:t>$(Xml-Escape $line)</a:t></a:r><a:endParaRPr lang=`"en-US`" sz=`"$($size * 100)`"$b/></a:p>"
    }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="Text $id"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="$(E $x)" y="$(E $y)"/><a:ext cx="$(E $w)" cy="$(E $h)"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody><a:bodyPr wrap="square" anchor="t"/><a:lstStyle/>$($paragraphs -join "")
  </p:txBody>
</p:sp>
"@
}

function Bullets-Shape(
    [int]$id,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [string[]]$items,
    [int]$size = 21,
    [string]$color = "DCE7F7"
) {
    $paragraphs = foreach ($item in $items) {
        "<a:p><a:pPr marL=`"285750`" indent=`"-171450`"><a:buChar char=`"•`"/></a:pPr><a:r><a:rPr lang=`"en-US`" sz=`"$($size * 100)`"><a:solidFill><a:srgbClr val=`"$color`"/></a:solidFill><a:latin typeface=`"Aptos`"/></a:rPr><a:t>$(Xml-Escape $item)</a:t></a:r><a:endParaRPr lang=`"en-US`" sz=`"$($size * 100)`"/></a:p>"
    }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="Bullets $id"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="$(E $x)" y="$(E $y)"/><a:ext cx="$(E $w)" cy="$(E $h)"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody><a:bodyPr wrap="square" anchor="t"/><a:lstStyle/>$($paragraphs -join "")
  </p:txBody>
</p:sp>
"@
}

function Bullets-Shape(
    [int]$id,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [string[]]$items,
    [int]$size = 21,
    [string]$color = "DCE7F7"
) {
    $paragraphs = foreach ($item in $items) {
        "<a:p><a:pPr marL=`"285750`" indent=`"-171450`"><a:buChar char=`"-`"/></a:pPr><a:r><a:rPr lang=`"en-US`" sz=`"$($size * 100)`"><a:solidFill><a:srgbClr val=`"$color`"/></a:solidFill><a:latin typeface=`"Aptos`"/></a:rPr><a:t>$(Xml-Escape $item)</a:t></a:r><a:endParaRPr lang=`"en-US`" sz=`"$($size * 100)`"/></a:p>"
    }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="Bullets $id"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="$(E $x)" y="$(E $y)"/><a:ext cx="$(E $w)" cy="$(E $h)"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody><a:bodyPr wrap="square" anchor="t"/><a:lstStyle/>$($paragraphs -join "")
  </p:txBody>
</p:sp>
"@
}

function Rect-Shape(
    [int]$id,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [string]$fill,
    [string]$line = "none",
    [int]$radius = 0
) {
    $ln = if ($line -eq "none") { "<a:ln><a:noFill/></a:ln>" } else { "<a:ln w=`"12700`"><a:solidFill><a:srgbClr val=`"$line`"/></a:solidFill></a:ln>" }
    $geom = if ($radius -gt 0) { "roundRect" } else { "rect" }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="Shape $id"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="$(E $x)" y="$(E $y)"/><a:ext cx="$(E $w)" cy="$(E $h)"/></a:xfrm><a:prstGeom prst="$geom"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="$fill"/></a:solidFill>$ln</p:spPr>
</p:sp>
"@
}

function Ellipse-Shape(
    [int]$id,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [string]$fill,
    [string]$line = "none"
) {
    $ln = if ($line -eq "none") { "<a:ln><a:noFill/></a:ln>" } else { "<a:ln w=`"12700`"><a:solidFill><a:srgbClr val=`"$line`"/></a:solidFill></a:ln>" }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="Node $id"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="$(E $x)" y="$(E $y)"/><a:ext cx="$(E $w)" cy="$(E $h)"/></a:xfrm><a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="$fill"/></a:solidFill>$ln</p:spPr>
</p:sp>
"@
}

function Image-Shape([int]$id, [string]$rid, [double]$x, [double]$y, [double]$w, [double]$h) {
    return @"
<p:pic>
  <p:nvPicPr><p:cNvPr id="$id" name="Image $id"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="$rid"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="$(E $x)" y="$(E $y)"/><a:ext cx="$(E $w)" cy="$(E $h)"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>
"@
}

function Flow-Box([int]$id, [double]$x, [double]$y, [double]$w, [string]$title, [string]$body, [string]$fill) {
    return (Rect-Shape $id $x $y $w 1.15 $fill "4B617C" 1) +
           (Text-Shape ($id + 100) ($x + .14) ($y + .13) ($w - .28) .28 @($title) 15 "FFFFFF" $true "ctr") +
           (Text-Shape ($id + 101) ($x + .16) ($y + .50) ($w - .32) .48 @($body) 11 "D7E6F4" $false "ctr")
}

$slides = @(
    @{
        Title = "HashVera Academic Record Network"
        Kicker = "Secure academic records with blockchain-style integrity"
        Kind = "title"
        Presenter = "Mohammad Afraz"
        RegisterNumber = "23BCAICD054"
        Department = "BCA - AI, CC & DevOps"
        College = "Yenepoya Institute of Arts, Science, Commerce and Management"
        Bullets = @("Flask + SQLite web application for EdTech workflows", "Campus identity, role-based access, tamper-evident ledger", "Certificate verification, audit logs, peer-node synchronization")
    },
    @{
        Title = "Problem Statement"
        Kind = "standard"
        Bullets = @("Academic documents can be edited or forged when stored as ordinary database rows.", "Manual verification is slow for colleges, students, and external verifiers.", "Traditional systems provide limited traceability after certificates or marksheets are issued.", "A single central system creates dependency and weakens trust during verification.")
        Accent = "F05D5E"
    },
    @{
        Title = "Project Aim And Objectives"
        Kind = "standard"
        Bullets = @("Design a secure academic record platform for EdTech environments.", "Bind every academic record to a SHA-256 hash chain for tamper detection.", "Provide usable workflows for Students, Faculty, Exam Cell, and Administrators.", "Support public certificate verification, audit visibility, backups, and peer sync.")
        Accent = "2CB67D"
    },
    @{
        Title = "Proposed Solution"
        Kind = "standard"
        Bullets = @("HashVera stores academic records as linked blocks instead of plain editable entries.", "Each block keeps record data, owner campus ID, timestamp, previous hash, current hash, nonce, and node signature.", "Verification recalculates hashes and detects changes in the stored chain.", "Authenticated peer sync demonstrates decentralized-style record sharing.")
        Accent = "7AA2FF"
    },
    @{
        Title = "Core Features"
        Kind = "grid"
        Cards = @(
            @("Campus Activation", "Preloaded campus directory binds each account to Campus ID and Campus Email ID."),
            @("Record Ledger", "Academic records are stored with hash chaining and certificate identifiers."),
            @("Review Queue", "Students submit requests; Faculty and Exam Cell review and approve them."),
            @("Public Verify", "Certificate ID or blockchain hash can be checked from public pages."),
            @("Admin Controls", "Users, peers, audit logs, backups, imports, exports, and email checks."),
            @("Notifications", "Account, record, request, and system events are visible inside the app.")
        )
    },
    @{
        Title = "Role-Based Access Model"
        Kind = "roles"
        Bullets = @("Student: views own records, submits new record and correction requests.", "Faculty: creates records and reviews student requests.", "Exam Cell: creates, edits, archives, restores, and approves records.", "Administrator: manages users, peers, audit, backups, imports, and exports.")
    },
    @{
        Title = "System Architecture"
        Kind = "architecture"
        Bullets = @("Browser renders Jinja templates and submits secure form requests.", "Flask blueprints separate auth, records, admin, public, and API concerns.", "SQLite stores users, records, campus directory, audit logs, tickets, and peers.", "HashVera API exposes health, chain, and sync endpoints for trusted peers.")
    },
    @{
        Title = "Technology Stack"
        Kind = "standard"
        Bullets = @("Backend: Python, Flask, Flask blueprints, Jinja templates.", "Database: SQLite with schema creation, runtime backfills, and demo seeding.", "Security: SHA-256 hash chain, HMAC peer signing, PBKDF2 password hashing, CSRF checks.", "Frontend: HTML, CSS, JavaScript, responsive dashboard and verification pages.")
        Accent = "00B8D9"
    },
    @{
        Title = "Blockchain-Style Record Flow"
        Kind = "flow"
        Steps = @(
            @("Create", "Authorized staff enters academic record details."),
            @("Hash", "Payload joins previous hash, timestamp, nonce, and owner."),
            @("Store", "Record block is saved with certificate ID and current hash."),
            @("Verify", "Chain verification detects any direct database tampering.")
        )
    },
    @{
        Title = "Campus Identity And Login"
        Kind = "image"
        Image = "docs\snapshots\01-login.png"
        Bullets = @("Login uses Campus Email ID and password.", "Record ownership is linked through Campus ID.", "Campus-style identity keeps the demo close to a real college workflow.")
    },
    @{
        Title = "Student Record Request Workflow"
        Kind = "workflow"
        Accent = "2CB67D"
        Steps = @(
            @("01", "Request", "Student submits a record or correction request."),
            @("02", "Review", "Faculty or Exam Cell checks the details."),
            @("03", "Mint", "Approved data enters the secure ledger."),
            @("04", "Notify", "Student gets the update and can verify it.")
        )
    },
    @{
        Title = "Certificate Verification"
        Kind = "image"
        Image = "docs\snapshots\03-public-verify.png"
        Bullets = @("Public users can verify certificates without logging in.", "Verification supports certificate IDs and blockchain hashes.", "The result proves authenticity against the stored ledger.")
    },
    @{
        Title = "Admin, Audit And Peer Sync"
        Kind = "image"
        Image = "docs\snapshots\04-public-audit.png"
        Bullets = @("Audit pages expose transparent activity history.", "Admin tools handle users, peers, backups, imports, exports, and email tests.", "Peer nodes communicate through authenticated API endpoints.")
    },
    @{
        Title = "Testing And Evaluation"
        Kind = "standard"
        Bullets = @("Test suite covers login, CSRF, campus activation, role permissions, and profile uploads.", "Record requests, review queues, notifications, backups, imports, and peer/admin actions are tested.", "Evaluation shows the system meets the project goal as a secure academic demonstration prototype.", "Known production extensions include HTTPS enforcement, rate limiting, managed storage, and stronger consensus.")
        Accent = "F9A826"
    },
    @{
        Title = "Conclusion And Future Scope"
        Kind = "standard"
        Bullets = @("HashVera demonstrates a practical blockchain-inspired approach to trusted academic records.", "It improves tamper evidence, auditability, verification speed, and institutional workflow control.", "Future scope: two-factor authentication, cloud object storage, PostgreSQL deployment, IPFS anchoring, digital signatures, and mobile app integration.", "The project is suitable for final-year demonstration, EdTech prototype discussion, and viva presentation.")
        Accent = "2CB67D"
    }
)

Ensure-Dir $build
Ensure-Dir (Join-Path $build "_rels")
Ensure-Dir (Join-Path $build "ppt\_rels")
Ensure-Dir (Join-Path $build "ppt\slides\_rels")
Ensure-Dir (Join-Path $build "ppt\slideLayouts\_rels")
Ensure-Dir (Join-Path $build "ppt\slideMasters\_rels")
Ensure-Dir (Join-Path $build "ppt\theme")
Ensure-Dir (Join-Path $build "ppt\media")

$logoPath = Join-Path $root "static\android-chrome-512x512.png"
Copy-Item $logoPath (Join-Path $build "ppt\media\logo.png") -Force

$collegeLogoPath = "C:\Users\appua\Downloads\yenepoya logo.jpeg"
$hasCollegeLogo = Test-Path $collegeLogoPath
if ($hasCollegeLogo) {
    Copy-Item $collegeLogoPath (Join-Path $build "ppt\media\college_logo.jpeg") -Force
}

$mediaIndex = 1
$imageMap = @{}
foreach ($s in $slides) {
    if ($s.ContainsKey("Image")) {
        $src = Join-Path $root $s.Image
        if (Test-Path $src) {
            $name = "screenshot$mediaIndex.png"
            Copy-Item $src (Join-Path $build "ppt\media\$name") -Force
            $imageMap[$s.Image] = $name
            $mediaIndex++
        }
    }
}

$contentTypes = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
"@
for ($i = 1; $i -le $slides.Count; $i++) {
    $contentTypes += "  <Override PartName=`"/ppt/slides/slide$i.xml`" ContentType=`"application/vnd.openxmlformats-officedocument.presentationml.slide+xml`"/>`n"
}
$contentTypes += "</Types>"
Write-Utf8 (Join-Path $build "[Content_Types].xml") $contentTypes

Write-Utf8 (Join-Path $build "_rels\.rels") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
"@

$sldIds = ""
$presRels = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
"@
for ($i = 1; $i -le $slides.Count; $i++) {
    $rid = $i + 1
    $sid = 255 + $i
    $sldIds += "<p:sldId id=`"$sid`" r:id=`"rId$rid`"/>"
    $presRels += "  <Relationship Id=`"rId$rid`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide`" Target=`"slides/slide$i.xml`"/>`n"
}
$presRels += "  <Relationship Id=`"rId$($slides.Count + 2)`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme`" Target=`"theme/theme1.xml`"/>`n</Relationships>"
Write-Utf8 (Join-Path $build "ppt\_rels\presentation.xml.rels") $presRels

Write-Utf8 (Join-Path $build "ppt\presentation.xml") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>$sldIds</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle><a:defPPr><a:defRPr lang="en-US"/></a:defPPr></p:defaultTextStyle>
</p:presentation>
"@

Write-Utf8 (Join-Path $build "ppt\slideMasters\slideMaster1.xml") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="0B1020"/></a:solidFill></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>
"@

Write-Utf8 (Join-Path $build "ppt\slideMasters\_rels\slideMaster1.xml.rels") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"@

Write-Utf8 (Join-Path $build "ppt\slideLayouts\slideLayout1.xml") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"@

Write-Utf8 (Join-Path $build "ppt\slideLayouts\_rels\slideLayout1.xml.rels") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"@

Write-Utf8 (Join-Path $build "ppt\theme\theme1.xml") @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="HashVera Theme">
  <a:themeElements>
    <a:clrScheme name="HashVera"><a:dk1><a:srgbClr val="0B1020"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="243B53"/></a:dk2><a:lt2><a:srgbClr val="DCE7F7"/></a:lt2><a:accent1><a:srgbClr val="00B8D9"/></a:accent1><a:accent2><a:srgbClr val="2CB67D"/></a:accent2><a:accent3><a:srgbClr val="F9A826"/></a:accent3><a:accent4><a:srgbClr val="F05D5E"/></a:accent4><a:accent5><a:srgbClr val="7AA2FF"/></a:accent5><a:accent6><a:srgbClr val="94A3B8"/></a:accent6><a:hlink><a:srgbClr val="00B8D9"/></a:hlink><a:folHlink><a:srgbClr val="7AA2FF"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="HashVera"><a:fillStyleLst><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="dk1"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>
"@

for ($i = 0; $i -lt $slides.Count; $i++) {
    $slideNum = $i + 1
    $s = $slides[$i]
    $accent = if ($s.ContainsKey("Accent")) { $s.Accent } else { "00B8D9" }
    $body = ""
    $body += Rect-Shape 2 0 0 13.333 7.5 "0B1020"
    $body += Rect-Shape 3 0 0 13.333 .18 $accent
    if ($s.Kind -ne "title") {
        $body += Image-Shape 4 "rLogo" 12.18 .34 .56 .56
        $body += Text-Shape 5 .64 .38 9.9 .45 @($s.Title) 27 "FFFFFF" $true
        $body += Rect-Shape 6 .64 .95 1.55 .06 $accent
    }

    switch ($s.Kind) {
        "title" {
            $body += Rect-Shape 7 7.45 .82 3.2 .03 "173A4B"
            $body += Rect-Shape 8 9.14 .82 .03 1.35 "173A4B"
            $body += Rect-Shape 9 9.14 2.17 2.55 .03 "173A4B"
            $body += Rect-Shape 10 10.72 2.17 .03 1.05 "173A4B"
            $body += Rect-Shape 11 1.25 5.92 2.7 .03 "173A4B"
            $body += Rect-Shape 12 2.28 4.82 .03 1.10 "173A4B"
            $body += Rect-Shape 13 2.28 4.82 2.25 .03 "173A4B"
            $body += Ellipse-Shape 14 7.33 .70 .22 .22 "2CB67D" "9FEAF5"
            $body += Ellipse-Shape 15 9.03 .70 .22 .22 "00B8D9" "9FEAF5"
            $body += Ellipse-Shape 16 10.60 2.05 .24 .24 "2CB67D" "9FEAF5"
            $body += Ellipse-Shape 17 10.60 3.10 .20 .20 "00B8D9" "9FEAF5"
            $body += Ellipse-Shape 18 1.13 5.80 .22 .22 "00B8D9" "9FEAF5"
            $body += Ellipse-Shape 19 2.17 4.70 .22 .22 "2CB67D" "9FEAF5"
            $body += Ellipse-Shape 20 4.42 4.70 .22 .22 "00B8D9" "9FEAF5"

            if ($hasCollegeLogo) {
                $body += Rect-Shape 21 .78 .54 2.55 1.12 "FFFFFF" "DCE7F7" 1
                $body += Image-Shape 22 "rCollegeLogo" .96 .70 2.18 .78
            }
            $body += Image-Shape 23 "rLogo" 11.82 .58 .72 .72

            $body += Text-Shape 30 .82 1.92 8.55 .42 @("Project Title") 14 "9FEAF5" $true
            $body += Text-Shape 31 .82 2.34 9.3 .98 @($s.Title) 39 "FFFFFF" $true
            $body += Text-Shape 32 .86 3.24 8.2 .38 @($s.Kicker) 17 "C9D7E8"
            $body += Rect-Shape 33 .86 3.82 1.75 .06 "2CB67D"

            $body += Rect-Shape 40 .86 4.30 5.75 1.92 "111D33" "314B67" 1
            $body += Text-Shape 41 1.15 4.55 1.70 .24 @("Presented by") 12 "9FEAF5" $true
            $body += Text-Shape 42 3.15 4.55 3.95 .24 @($s.Presenter) 13 "FFFFFF"
            $body += Text-Shape 43 1.15 4.93 1.70 .24 @("Register No.") 12 "9FEAF5" $true
            $body += Text-Shape 44 3.15 4.93 3.95 .24 @($s.RegisterNumber) 13 "FFFFFF"
            $body += Text-Shape 45 1.15 5.31 1.70 .24 @("Department") 12 "9FEAF5" $true
            $body += Text-Shape 46 3.15 5.31 3.95 .24 @($s.Department) 13 "FFFFFF"
            $body += Text-Shape 47 1.15 5.69 1.70 .24 @("College") 12 "9FEAF5" $true
            $body += Text-Shape 48 3.15 5.69 3.95 .24 @($s.College) 11 "FFFFFF"

            $body += Rect-Shape 60 8.42 4.12 3.38 1.86 "102135" "2E6A7B" 1
            $body += Text-Shape 61 8.78 4.43 2.70 .30 @("Blockchain Focus") 18 "FFFFFF" $true "ctr"
            $body += Text-Shape 62 8.72 4.92 2.82 .62 @("Tamper-evident records", "hash chain verification", "trusted academic workflow") 13 "C9D7E8" $false "ctr"
        }
        "grid" {
            $positions = @(@(.78,1.38), @(.78,3.05), @(.78,4.72), @(6.95,1.38), @(6.95,3.05), @(6.95,4.72))
            for ($c = 0; $c -lt $s.Cards.Count; $c++) {
                $p = $positions[$c]
                $body += Rect-Shape (20 + $c) $p[0] $p[1] 5.4 1.22 "111D33" "314B67" 1
                $body += Text-Shape (60 + $c) ($p[0] + .22) ($p[1] + .16) 4.95 .25 @($s.Cards[$c][0]) 16 "FFFFFF" $true
                $body += Text-Shape (80 + $c) ($p[0] + .22) ($p[1] + .52) 4.92 .46 @($s.Cards[$c][1]) 12 "C9D7E8"
            }
        }
        "roles" {
            $body += Bullets-Shape 20 .85 1.35 5.9 3.6 $s.Bullets 19 "DCE7F7"
            $body += Flow-Box 35 7.3 1.48 1.35 "Student" "Own records and requests" "14305A"
            $body += Flow-Box 38 9.1 1.48 1.35 "Faculty" "Record creation and review" "1C3F52"
            $body += Flow-Box 41 7.3 3.18 1.35 "Exam Cell" "Edit, archive and restore" "32533B"
            $body += Flow-Box 44 9.1 3.18 1.35 "Admin" "Governance and operations" "4A2B43"
            $body += Text-Shape 55 7.0 5.15 3.8 .62 @("Permissions keep official records controlled while students stay involved in the workflow.") 15 "9FEAF5" $false "ctr"
        }
        "architecture" {
            $body += Flow-Box 20 .75 2.05 1.75 "Browser" "Forms, dashboards, verification pages" "14305A"
            $body += Flow-Box 24 3.38 2.05 1.75 "Flask App" "Blueprint routes and service helpers" "1C3F52"
            $body += Flow-Box 28 6.02 2.05 1.75 "SQLite" "Users, records, audit, peers" "32533B"
            $body += Flow-Box 32 8.65 2.05 1.75 "Peer Node" "Authenticated chain sync" "4A2B43"
            $body += Text-Shape 44 2.58 2.42 .55 .3 @("->") 24 "9FEAF5" $true "ctr"
            $body += Text-Shape 45 5.22 2.42 .55 .3 @("->") 24 "9FEAF5" $true "ctr"
            $body += Text-Shape 46 7.85 2.42 .55 .3 @("<->") 22 "9FEAF5" $true "ctr"
            $body += Bullets-Shape 50 .98 4.55 10.9 1.15 $s.Bullets 15 "DCE7F7"
        }
        "flow" {
            $x = .78
            for ($c = 0; $c -lt $s.Steps.Count; $c++) {
                $step = $s.Steps[$c]
                $body += Flow-Box (20 + ($c * 5)) $x 2.35 2.35 $step[0] $step[1] "111D33"
                if ($c -lt 3) { $body += Text-Shape (80 + $c) ($x + 2.42) 2.72 .45 .25 @("->") 22 "9FEAF5" $true "ctr" }
                $x += 3.05
            }
            $body += Text-Shape 70 1.15 4.55 10.9 .8 @("The important point: if any older block is changed, every later hash no longer matches, so verification exposes tampering.") 18 "FFFFFF" $false "ctr"
        }
        "workflow" {
            $body += Text-Shape 20 .88 1.24 7.2 .42 @("From Request To Verified Record") 24 "FFFFFF" $true
            $body += Text-Shape 21 .92 1.78 6.4 .30 @("A simple approval path keeps student input and staff control separate.") 13 "C9D7E8"

            $positions = @(
                @(.92, 2.55),
                @(6.86, 2.55),
                @(.92, 4.42),
                @(6.86, 4.42)
            )
            for ($c = 0; $c -lt $s.Steps.Count; $c++) {
                $step = $s.Steps[$c]
                $p = $positions[$c]
                $body += Rect-Shape (30 + ($c * 7)) $p[0] $p[1] 4.75 1.18 "111D33" "314B67" 1
                $body += Rect-Shape (31 + ($c * 7)) ($p[0] + .24) ($p[1] + .29) .58 .58 "2CB67D" "2CB67D" 1
                $body += Text-Shape (32 + ($c * 7)) ($p[0] + .34) ($p[1] + .42) .38 .16 @($step[0]) 10 "0B1020" $true "ctr"
                $body += Text-Shape (33 + ($c * 7)) ($p[0] + 1.05) ($p[1] + .23) 3.15 .24 @($step[1]) 18 "FFFFFF" $true
                $body += Text-Shape (34 + ($c * 7)) ($p[0] + 1.05) ($p[1] + .63) 3.28 .24 @($step[2]) 11 "C9D7E8"
            }

            $body += Text-Shape 60 6.02 3.05 .55 .22 @("->") 20 "9FEAF5" $true "ctr"
            $body += Text-Shape 61 3.15 3.83 .55 .22 @("v") 18 "9FEAF5" $true "ctr"
            $body += Text-Shape 62 9.10 3.83 .55 .22 @("v") 18 "9FEAF5" $true "ctr"
            $body += Text-Shape 63 6.02 4.92 .55 .22 @("->") 20 "9FEAF5" $true "ctr"

            $body += Rect-Shape 70 1.35 6.08 10.6 .50 "102135" "2E6A7B" 1
            $body += Text-Shape 71 1.72 6.22 9.85 .18 @("Result: approved, traceable records that students can present and verifiers can trust.") 12 "9FEAF5" $false "ctr"
        }
        "image" {
            $imgName = $imageMap[$s.Image]
            if ($imgName) {
                $body += Rect-Shape 20 .78 1.34 7.15 4.72 "111827" "2E6A7B" 1
                $body += Image-Shape 21 "rShot" .95 1.52 6.8 4.36
            }
            $body += Bullets-Shape 30 8.28 1.58 4.25 2.55 $s.Bullets 18 "DCE7F7"
            $body += Rect-Shape 31 8.32 4.72 3.72 .92 "102135" "2E6A7B" 1
            $body += Text-Shape 32 8.58 4.95 3.2 .32 @("Live UI Evidence") 17 "9FEAF5" $true "ctr"
        }
        default {
            $body += Bullets-Shape 20 .95 1.48 7.15 4.55 $s.Bullets 21 "DCE7F7"
            $body += Rect-Shape 35 9.0 1.65 2.45 2.45 "111D33" $accent 1
            $body += Text-Shape 36 9.28 2.18 1.92 .78 @(("{0:D2}" -f $slideNum)) 44 $accent $true "ctr"
            $body += Text-Shape 37 8.75 4.45 3.0 .7 @("HashVera", "Academic Record Network") 17 "FFFFFF" $true "ctr"
        }
    }

    $body += Text-Shape 990 10.95 6.95 1.55 .25 @("Slide $slideNum / 15") 9 "7D91AA" $false "r"

    $slideXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>$body</p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"@
    Write-Utf8 (Join-Path $build "ppt\slides\slide$slideNum.xml") $slideXml

    $relXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rLogo" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/logo.png"/>
"@
    if (($s.Kind -eq "image" -or $s.Kind -eq "activation") -and $imageMap[$s.Image]) {
        $relXml += "  <Relationship Id=`"rShot`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image`" Target=`"../media/$($imageMap[$s.Image])`"/>`n"
    }
    if ($slideNum -eq 1 -and $hasCollegeLogo) {
        $relXml += "  <Relationship Id=`"rCollegeLogo`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image`" Target=`"../media/college_logo.jpeg`"/>`n"
    }
    $relXml += "</Relationships>"
    Write-Utf8 (Join-Path $build "ppt\slides\_rels\slide$slideNum.xml.rels") $relXml
}

if (Test-Path $outFile) {
    Remove-Item -LiteralPath $outFile -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($outFile, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -Path $build -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($build.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $relative) | Out-Null
    }
} finally {
    $zip.Dispose()
}

Write-Host "Created $outFile"
