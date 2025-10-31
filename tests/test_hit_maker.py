import os
from chord_striker.hit_maker import create_song, create_album


def test_create_song(test_output_dir, test_seed, test_key, test_tempo):
    """Test creating a single song."""
    song_name = "test_song"
    create_song(
        key=test_key,
        tempo=test_tempo,
        seed=test_seed,
        song_name=song_name,
        output_dir=test_output_dir,
    )

    # Check that files were created
    assert os.path.exists(os.path.join(test_output_dir, f"{song_name}.pdf"))
    assert os.path.exists(os.path.join(test_output_dir, f"{song_name}.midi"))
    assert os.path.exists(os.path.join(test_output_dir, f"{song_name}.ly"))


def test_create_album(test_output_dir, test_seed):
    """Test creating an album."""
    num_songs = 3
    create_album(num_songs, seeds=[test_seed] * num_songs, parent_dir=test_output_dir)

    # Check that all songs were created
    for i in range(num_songs):
        song_name = str(i + 1)
        song_dir = os.path.join(test_output_dir, song_name)
        assert os.path.exists(os.path.join(song_dir, f"{song_name}.pdf"))
        assert os.path.exists(os.path.join(song_dir, f"{song_name}.midi"))
        assert os.path.exists(os.path.join(song_dir, f"{song_name}.ly"))


def test_create_song_random_params(test_output_dir):
    """Test creating a song with random parameters."""
    song_name = "random_song"
    create_song(
        key=None,  # Random key
        tempo=None,  # Random tempo
        seed=None,  # Random seed
        song_name=song_name,
        output_dir=test_output_dir,
    )

    # Check that files were created
    assert os.path.exists(os.path.join(test_output_dir, f"{song_name}.pdf"))
    assert os.path.exists(os.path.join(test_output_dir, f"{song_name}.midi"))
    assert os.path.exists(os.path.join(test_output_dir, f"{song_name}.ly"))
