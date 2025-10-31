"""Helper functions for accessing package resources."""

from pathlib import Path


def get_package_root():
    """Get the root directory of the installed package."""
    # Use __file__ from this module to find package root
    return Path(__file__).parent


def get_constants_dir(custom_dir=None):
    """
    Get the path to the constants directory.

    Args:
        custom_dir: Optional custom directory path. If provided, uses that
            instead of the package defaults.

    Returns:
        Path to the constants directory.
    """
    if custom_dir is not None:
        return Path(custom_dir)

    # Try to find constants in package
    package_root = get_package_root()
    constants_dir = package_root / "constants" / "defaults"

    if constants_dir.exists():
        return constants_dir

    # Fallback to old location (for backward compatibility)
    fallback = Path("constants/defaults")
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        "Could not find constants directory. "
        "Please specify a custom constants_dir or ensure package is properly installed."
    )


def get_lilypond_assets_dir():
    """
    Get the path to the lilypond_assets directory.

    Returns:
        Path to the lilypond_assets directory.
    """
    package_root = get_package_root()
    assets_dir = package_root / "lilypond_assets"

    if assets_dir.exists():
        return assets_dir

    # Fallback to old location (for backward compatibility)
    fallback = Path("lilypond_assets")
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        "Could not find lilypond_assets directory. "
        "Please ensure package is properly installed."
    )
