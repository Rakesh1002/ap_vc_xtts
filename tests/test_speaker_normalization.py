import pytest
import torch
import torchaudio
import io
import logging
from app.services.storage_service import StorageService
from app.core.config import get_settings
import numpy as np
from scipy.io import wavfile

logger = logging.getLogger(__name__)
settings = get_settings()

def normalize_audio(waveform: np.ndarray, target_db: float = -18.0) -> np.ndarray:
    """Quick RMS normalization with peak limiting"""
    # Calculate current RMS
    rms = np.sqrt(np.mean(np.square(waveform)))
    
    # Calculate target RMS (convert from dB)
    target_rms = 10 ** (target_db / 20.0)
    
    # Calculate gain needed
    gain = target_rms / (rms + 1e-6)  # Avoid division by zero
    
    # Apply gain
    normalized = waveform * gain
    
    # Apply peak limiting to prevent clipping
    max_peak = np.max(np.abs(normalized))
    if max_peak > 0.95:  # Leave some headroom
        normalized = normalized * (0.95 / max_peak)
    
    return normalized

@pytest.mark.asyncio
async def test_speaker_normalization():
    """Test speaker audio normalization workflow"""
    try:
        # Initialize storage service
        storage = StorageService()
        
        # Source and destination paths
        source_path = "processed/5370428f-ad2a-4582-bdef-8a66eb6a553e/speaker_0.wav"
        normalized_path = "processed/5370428f-ad2a-4582-bdef-8a66eb6a553e/speaker_0_normalized.wav"
        
        # Download original audio
        logger.info(f"Downloading audio from {source_path}")
        audio_data = await storage.download_file(source_path)
        
        # Load audio
        with io.BytesIO(audio_data) as buffer:
            # Load with torchaudio
            waveform, sample_rate = torchaudio.load(buffer)
            
            # Convert to mono if stereo
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Convert to numpy for processing
            audio_np = waveform.numpy().T
            
            # Get original stats
            original_rms = np.sqrt(np.mean(np.square(audio_np)))
            original_peak = np.max(np.abs(audio_np))
            logger.info(f"Original stats - RMS: {20 * np.log10(original_rms):.2f} dB, Peak: {original_peak:.2f}")
            
            # Normalize audio
            normalized = normalize_audio(
                audio_np,
                target_db=-18.0  # Target RMS level
            )
            
            # Get final stats
            final_rms = np.sqrt(np.mean(np.square(normalized)))
            final_peak = np.max(np.abs(normalized))
            logger.info(f"Final stats - RMS: {20 * np.log10(final_rms):.2f} dB, Peak: {final_peak:.2f}")
            
            # Save normalized audio
            buffer = io.BytesIO()
            wavfile.write(
                buffer,
                sample_rate,
                (normalized * np.iinfo(np.int16).max).astype(np.int16)
            )
            buffer.seek(0)
            
            # Upload normalized version
            await storage.upload_file(buffer.getvalue(), normalized_path)
            logger.info(f"Uploaded normalized audio to {normalized_path}")
            
            # Generate pre-signed URL
            url = await storage.get_presigned_url(normalized_path)
            logger.info(f"Pre-signed URL for normalized audio: {url}")
            
            # Return results for assertions
            result = {
                "original_path": source_path,
                "normalized_path": normalized_path,
                "original_rms_db": float(20 * np.log10(original_rms)),
                "final_rms_db": float(20 * np.log10(final_rms)),
                "original_peak": float(original_peak),
                "final_peak": float(final_peak),
                "download_url": url
            }
            
            # Add assertions
            assert result["final_rms_db"] > -24.0, "Final RMS should not be too quiet"
            assert abs(result["final_rms_db"] - (-18.0)) < 1.0, "Final RMS should be close to target"
            assert result["final_peak"] <= 0.95, "Peak should not exceed -0.5 dB"
            
            return result
            
    except Exception as e:
        logger.error(f"Error in speaker normalization test: {str(e)}")
        raise

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run test
    import asyncio
    result = asyncio.run(test_speaker_normalization())
    
    # Print detailed results
    print("\nNormalization Results:")
    print(f"Original RMS: {result['original_rms_db']:.2f} dB")
    print(f"Final RMS: {result['final_rms_db']:.2f} dB")
    print(f"Original Peak: {result['original_peak']:.2f}")
    print(f"Final Peak: {result['final_peak']:.2f}")
    print(f"\nDownload normalized audio:")
    print(result['download_url']) 