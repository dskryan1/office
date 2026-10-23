"""
Coletor de inventario - Office Telco.
Roda NA MAQUINA que sera inventariada e envia os dados para o painel central.
Uso:  python coletor.py 10.70.2.118
"""
import os
import sys
import json
import socket
import platform
import subprocess
import urllib.request
from datetime import datetime

PORTA = 8502
TOKEN_COLETA = "ryan123"   # precisa ser igual no painel e no coletor (esta e a unica definicao)


def coletar_inventario():
    """Coleta dados detalhados do computador local com o nome exato do processador."""
    host = os.environ.get("COMPUTERNAME") or platform.node() or "Não identificado"
    try:
        user = os.environ.get("USERNAME") or os.getlogin()
    except Exception:
        user = os.environ.get("USERNAME", "Não identificado")

    system_name = platform.system()
    windows_version = platform.version()
    cpu = "Não identificado"
    mem_type = "Não identificado"
    disk_type = "Não identificado"
    disk_total_gb = None

    try:
        ps_script = r'''
        $ErrorActionPreference = 'SilentlyContinue'
        $os = Get-CimInstance -ClassName Win32_OperatingSystem
        $processor = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
        $mem = Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object -First 1
        $disk = Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -First 1
        
        $ramTypeStr = "Não identificado"
        if ($mem) {
            $smb = $mem.SMBIOSMemoryType
            if ($smb -eq 20) { $ramTypeStr = "DDR" }
            elseif ($smb -eq 21) { $ramTypeStr = "DDR2" }
            elseif ($smb -eq 24) { $ramTypeStr = "DDR3" }
            elseif ($smb -eq 26) { $ramTypeStr = "DDR4" }
            elseif ($smb -eq 34) { $ramTypeStr = "DDR5" }
            else {
                $mt = $mem.MemoryType
                if ($mt -eq 20) { $ramTypeStr = "DDR" }
                elseif ($mt -eq 21) { $ramTypeStr = "DDR2" }
                elseif ($mt -eq 24) { $ramTypeStr = "DDR3" }
                elseif ($mt -eq 26) { $ramTypeStr = "DDR4" }
                elseif ($mt -eq 34) { $ramTypeStr = "DDR5" }
            }
        }

        $dTypeStr = "Não identificado"
        $physicalDisk = Get-PhysicalDisk | Select-Object -First 1
        if ($physicalDisk -and $physicalDisk.MediaType) {
            $dTypeStr = $physicalDisk.MediaType
        } else {
            if ($disk -and $disk.Model) {
                if ($disk.Model -match "SSD" -or $disk.Model -match "NVMe") {
                    $dTypeStr = "SSD"
                } else {
                    $dTypeStr = "HDD (HD)"
                }
            }
        }

        [PSCustomObject]@{
          Caption = $os.Caption
          Version = $os.Version
          Build = $os.BuildNumber
          CPU = $processor.Name.Trim()
          RAMType = $ramTypeStr
          DiskType = $dTypeStr
          DiskSizeGB = [math]::Round($disk.Size / 1GB, 2)
        } | ConvertTo-Json -Compress
        '''
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=15, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            details = json.loads(result.stdout.strip())
            system_name = details.get("Caption") or system_name
            windows_version = "{} (compilação {})".format(
                details.get("Version") or platform.version(),
                details.get("Build") or "?"
            )
            cpu_raw = (details.get("CPU") or "").strip()
            if cpu_raw:
                cpu = cpu_raw
            mem_type = details.get("RAMType") or "Não identificado"
            disk_type = details.get("DiskType") or "Não identificado"
            disk_total_gb = details.get("DiskSizeGB")
    except Exception:
        pass

    cpu_friendly = cpu

    ip = "Não identificado"
    mem = None
    disk_free_gb = None
    try:
        import psutil
        for addresses in psutil.net_if_addrs().values():
            for addr in addresses:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    ip = addr.address
                    break
            if ip != "Não identificado":
                break
        mem = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        drive = os.environ.get("SystemDrive", "C:")
        disk_info = psutil.disk_usage(drive + "\\")
        disk_free_gb = round(disk_info.free / (1024 ** 3), 2)
        if not disk_total_gb:
            disk_total_gb = round(disk_info.total / (1024 ** 3), 2)
    except Exception:
        pass

    return {
        "coletado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hostname": host,
        "usuario": user,
        "sistema": system_name,
        "versao": windows_version,
        "processador": cpu_friendly,
        "memoria_gb": mem,
        "memoria_tipo": mem_type,
        "disco_tipo": disk_type,
        "disco_tamanho_gb": disk_total_gb,
        "disco_livre_gb": disk_free_gb,
        "ipv4": ip,
        "origem": "Coleta local"
    }


def enviar(servidor, info):
    url = f"http://{servidor}:{PORTA}/inventario"
    req = urllib.request.Request(
        url,
        data=json.dumps(info).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Token": TOKEN_COLETA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status == 200


if __name__ == "__main__":
    if len(sys.argv) < 2 or "COLOQUE_AQUI" in sys.argv[1]:
        print("Informe o IP ou nome do computador da TI. Exemplo: python coletor.py 192.168.0.10")
        sys.exit(1)
    info = coletar_inventario()
    info["origem"] = "Coleta remota"
    print("Dados coletados nesta maquina:", info["hostname"], "|", info["processador"])
    try:
        enviar(sys.argv[1], info)
        print("Inventario enviado com sucesso para a TI. Obrigado!")
    except Exception as exc:
        print("Nao foi possivel enviar o inventario:", exc)
        print("Verifique se o painel esta ligado e se a porta", PORTA, "esta liberada no firewall do PC da TI.")
        sys.exit(2)
