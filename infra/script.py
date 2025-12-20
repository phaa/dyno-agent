from pathlib import Path

def concat_files(
    output_file: str = "output.txt",
    ignore_extensions: set = None,
    ignore_dirs: set = None
):
    # Pasta onde ESTE script está
    root = Path.cwd().resolve()

    ignore_extensions = ignore_extensions or {
        ".py", ".exe", ".dll", ".so", ".png", ".jpg",
        ".jpeg", ".gif", ".zip", ".tar", ".gz", ".pdf", ".terraform.lock.hcl", ".tfplan"
    }

    ignore_dirs = ignore_dirs or {
        ".git", ".venv", "venv", "__pycache__", "node_modules", ".terraform"
    }

    output_path = root / output_file

    print(output_path)
    

    with open(output_path, "w", encoding="utf-8") as out:
        for path in sorted(root.rglob("*")):

            # Ignora diretórios indesejados
            if path.is_dir():
                if path.name in ignore_dirs:
                    continue
                continue

            # Ignora o próprio arquivo de saída
            if path.resolve() == output_path.resolve():
                continue

            # Ignora extensões indesejadas
            if path.suffix in ignore_extensions:
                continue

            try:
                relative_path = path.relative_to(root)
                
                if relative_path.parts[0] in ignore_dirs:
                    
                    continue

                out.write(f"\n# {relative_path}\n\n")

                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    out.write(f.read())

                out.write("\n\n")

            except Exception as e:
                out.write(f"\n# {relative_path} - ERRO AO LER ARQUIVO: {e}\n\n")


if __name__ == "__main__":
    concat_files()
