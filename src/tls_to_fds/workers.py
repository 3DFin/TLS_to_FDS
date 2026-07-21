from PySide6.QtCore import QThread, Signal
import traceback
from tls_to_fds.main import run_pipeline


class PipelineWorker(QThread):
    """
    Background thread to execute the FDS voxelization pipeline.
    Prevents the main GUI from freezing during heavy 3D processing.
    """

    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal()

    def __init__(self, runtime_config):
        super().__init__()
        self.config = runtime_config

    def run(self):
        # We pass a lambda function so the pipeline's print statements
        # emit our Qt Signal instead of printing to the hidden system console.
        try:
            run_pipeline(
                self.config,
                log_callback=lambda msg: self.log_signal.emit(str(msg)),
                progress_callback=lambda val: self.progress_signal.emit(int(val)),
            )
        except Exception:
            # Print the full error stack trace so we know exactly why it froze
            err_msg = traceback.format_exc()
            self.log_signal.emit(f"FATAL ERROR: Pipeline crashed:\\n{err_msg}")
        finally:
            self.finished_signal.emit()
