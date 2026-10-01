import importlib
import inspect
import pkgutil
from typing import List

from .base import BaseCollector

def get_all_collectors() -> List[BaseCollector]:
    """
    Dynamically discover and instantiate all collectors in this package.
    """
    collectors = []
    # Iterate through all modules in the current package
    package_name = __name__
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        full_module_name = f"{package_name}.{module_name}"
        module = importlib.import_module(full_module_name)
        
        # Find all classes in the module that inherit from BaseCollector
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseCollector) and obj is not BaseCollector:
                # Instantiate the collector and add to list
                collectors.append(obj())
                
    return collectors
