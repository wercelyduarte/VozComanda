# -*- coding: utf-8 -*-
r"""
Empacota o build do cx_Freeze como .msix para a Microsoft Store.

  python setup.py build_exe   (ou bdist_msi)  -> build\VozComanda\
  python build_msix.py                        -> dist\VozComanda-X.Y.Z.msix

O pacote sai sem assinatura: a Store assina ao publicar. Os valores de identidade vem de
Partner Center > VozComanda > Identidade do produto.
"""
import glob
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image

IDENTITY_NAME   = "WDSoftware.VozComanda"
PUBLISHER       = "CN=9D10F0A4-908D-48F7-8443-E79125171516"
PUBLISHER_NAME  = "WD Software"
DISPLAY_NAME    = "VozComanda"
DESCRIPTION     = "Ditado por voz para agentes de IA, com tradução"

ROOT    = Path(__file__).parent
BUILD   = ROOT / "build" / "VozComanda"
STAGE   = ROOT / "build" / "msix"
LOGOS   = {"Square44x44Logo.png": 44, "Square150x150Logo.png": 150, "StoreLogo.png": 50}

# The app keeps config.json and the Whisper models in %LOCALAPPDATA%\VozComanda; the default
# AppData virtualization moves them into the package's own storage, which Windows removes
# on uninstall. comando.txt goes to a folder the user picks, outside AppData.
# The microphone capability puts the app under Settings > Privacy > Microphone.
MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name="{name}" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{display}</DisplayName>
    <PublisherDisplayName>{publisher_name}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="pt-BR" />
  </Resources>
  <Applications>
    <Application Id="VozComanda" Executable="VozComanda.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{display}" Description="{description}" BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" />
    </Application>
  </Applications>
  <Capabilities>
    <Capability Name="internetClient" />
    <rescap:Capability Name="runFullTrust" />
    <DeviceCapability Name="microphone" />
  </Capabilities>
</Package>
"""


def makeappx() -> str:
    found = sorted(glob.glob(r"C:\Program Files (x86)\Windows Kits\10\bin\10.*\x64\makeappx.exe"))
    if not found:
        sys.exit("makeappx.exe nao encontrado (instale o Windows SDK)")
    return found[-1]


def main():
    if not (BUILD / "VozComanda.exe").exists():
        sys.exit(f"{BUILD} nao existe: rode antes  python setup.py build_exe")
    version = (BUILD / "VERSION").read_text(encoding="utf-8").strip()
    msix_version = ".".join((version.split(".") + ["0"] * 4)[:3]) + ".0"   # Store wants X.Y.Z.0

    shutil.rmtree(STAGE, ignore_errors=True)
    shutil.copytree(BUILD, STAGE)
    (STAGE / "Assets").mkdir()
    icon = Image.open(ROOT / "icone.ico")
    icon.size = max(icon.info["sizes"])     # the .ico holds 16..256 px; draw from the largest
    icon = icon.convert("RGBA")
    for filename, size in LOGOS.items():
        icon.resize((size, size), Image.LANCZOS).save(STAGE / "Assets" / filename)
    (STAGE / "AppxManifest.xml").write_text(MANIFEST.format(
        name=IDENTITY_NAME, publisher=escape(PUBLISHER), version=msix_version, display=DISPLAY_NAME,
        publisher_name=PUBLISHER_NAME, description=escape(DESCRIPTION)), encoding="utf-8")

    out = ROOT / "dist" / f"VozComanda-{version}.msix"
    out.parent.mkdir(exist_ok=True)
    subprocess.run([makeappx(), "pack", "/o", "/d", str(STAGE), "/p", str(out)], check=True)
    print(out)


if __name__ == "__main__":
    main()
