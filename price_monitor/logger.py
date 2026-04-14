import logging
import colorlog
from .config import Config

def setup_logger(name: str) -> logging.Logger:
    config = Config()
    log_level = config.get('logging.level', 'INFO')
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    
    color_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)
    
    return logger
