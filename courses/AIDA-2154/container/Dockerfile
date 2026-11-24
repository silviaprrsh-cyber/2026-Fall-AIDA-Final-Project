# escape=`
FROM mcr.microsoft.com/windows/servercore:ltsc2022
SHELL ["powershell", "-NoLogo", "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR C:/app
COPY container/install-runtime.ps1 C:/app/install-runtime.ps1
RUN & C:/app/install-runtime.ps1; Remove-Item -LiteralPath C:/app/install-runtime.ps1
COPY container/requirements.txt C:/app/requirements.txt
RUN & C:/Python/python.exe -m pip install --no-cache-dir -r C:/app/requirements.txt; if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }; & C:/Python/python.exe -c 'import numpy,torch; print(numpy.__version__, torch.__version__)'; if ($LASTEXITCODE -ne 0) { throw 'Runtime import check failed' }
COPY src/cv_tools/model.py C:/app/cv_model.py
COPY container/infer.py C:/app/infer.py
USER ContainerUser
ENTRYPOINT ["C:/Python/python.exe", "-B", "C:/app/infer.py"]
