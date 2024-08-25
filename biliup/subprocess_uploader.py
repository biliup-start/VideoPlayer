import subprocess

from DMR.utils import VideoInfo, replace_keywords


class SubprocessUploader:
    def __init__(self) -> None:
        self.procs = {}

    def call_subprocess(self, file, command, timeout=None, **kwargs):
        cmds = [replace_keywords(str(x), file) for x in command]
        proc = subprocess.Popen(cmds)
        self.procs[proc.pid] = proc
        status, message = False, ''
        try:
            if timeout:
                proc.wait(timeout=timeout)
            else:
                proc.wait()
            status = proc.returncode == 0
            message = f'Process {cmds} return code: {proc.returncode}'
        except subprocess.TimeoutExpired:
            status = False
            proc.kill()
            message = f'Process {cmds} timeout after {timeout} seconds'
        finally:
            self.procs.pop(proc.pid)
        return status, message

    def upload(self, files:list[VideoInfo], **kwargs):
        if not isinstance(files, list):
            files = [files]

        status, message = False, ''
        for file in files:
            try:
                sts, msg = self.call_subprocess(file, **kwargs)
                status = status and sts
                if sts:
                    message += f'File {file.path} upload success.\n'
                else:
                    message += f'File {file.path} upload failed: {msg}\n'
            except Exception as e:
                status= False
                message += f'File {file.path} upload raise an error: {e}\n'
            
        return status, message.strip()
