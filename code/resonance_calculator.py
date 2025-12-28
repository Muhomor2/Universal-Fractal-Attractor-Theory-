#!/usr/bin/env python3
"""
resonance_calculator.py
=======================
LRD v6.3 — Universal Fractal Attractor

Calculates the Resonance Index and predicted pareidolia probability
based on the Resonance Perception Theorem.

Part of the Universal Fractal Attractor Theory
Author: Igor Chechelnitsky (ORCID: 0009-0007-4607-1946)
License: CC BY 4.0

Usage:
    python resonance_calculator.py --D_ext 1.25 --D_int 1.35
    python resonance_calculator.py --H_ext 0.75 --H_int 0.65
    python resonance_calculator.py --image image.png

Theory:
    The Resonance Perception Theorem states that pattern recognition
    probability follows:
    
        P_rec ∝ exp(-(D_ext - D*)² / 2σ²)
    
    where D* ≈ 1.30 is the attractor point and σ ≈ 0.08 is the bandwidth.
"""

import argparse
import numpy as np
import sys

# =============================================================================
# Constants: Universal Fractal Attractor
# =============================================================================

D_ATTRACTOR = 1.30      # Universal Fractal Attractor dimension
H_ATTRACTOR = 0.70      # Equivalent Hurst exponent (D = 2 - H)
D_NEURAL = 1.35         # Typical neural fractal dimension
H_NEURAL = 0.65         # Typical neural Hurst exponent
SIGMA_D = 0.08          # Resonance bandwidth (standard deviation)
P_MAX = 0.65            # Maximum recognition probability


# =============================================================================
# Core Functions
# =============================================================================

def hurst_to_dimension(H):
    """
    Convert Hurst exponent to fractal dimension.
    
    For 1D time series and 2D contours (E=1):
        D = 2 - H
    """
    return 2.0 - H


def dimension_to_hurst(D):
    """
    Convert fractal dimension to Hurst exponent.
    
        H = 2 - D
    """
    return 2.0 - D


def resonance_index(D_ext, D_int=D_NEURAL):
    """
    Calculate the Resonance Index.
    
    R = 1 - |D_ext - D_int| / D_int
    
    Parameters:
        D_ext: External stimulus fractal dimension
        D_int: Internal (neural) fractal dimension (default: 1.35)
    
    Returns:
        R: Resonance index in [0, 1] (higher = better match)
    """
    R = 1.0 - abs(D_ext - D_int) / D_int
    return max(0.0, min(1.0, R))  # Clamp to [0, 1]


def pareidolia_probability(D_ext, D_star=D_ATTRACTOR, sigma=SIGMA_D, p_max=P_MAX):
    """
    Predict pareidolia probability using the Resonance Perception Theorem.
    
    P_rec = P_max * exp(-(D_ext - D*)² / 2σ²)
    
    Parameters:
        D_ext: External stimulus fractal dimension
        D_star: Attractor point (default: 1.30)
        sigma: Resonance bandwidth (default: 0.08)
        p_max: Maximum probability (default: 0.65)
    
    Returns:
        P_rec: Predicted recognition probability
    """
    exponent = -((D_ext - D_star) ** 2) / (2 * sigma ** 2)
    return p_max * np.exp(exponent)


def spectral_exponent(H):
    """
    Calculate power spectral exponent from Hurst exponent.
    
    S(f) ~ f^(-β), where β = 2H - 1
    """
    return 2 * H - 1


def coding_entropy_relative(H, H_star=H_ATTRACTOR):
    """
    Calculate relative coding entropy.
    
    H_code(H) = H_0 * |H - H*|² + O(|H-H*|³)
    
    Returns normalized value (0 = optimal).
    """
    return (H - H_star) ** 2


# =============================================================================
# Analysis Functions
# =============================================================================

def full_analysis(D_ext=None, H_ext=None, D_int=D_NEURAL, verbose=True):
    """
    Perform complete resonance analysis.
    
    Provide either D_ext or H_ext (not both).
    """
    # Convert if needed
    if D_ext is None and H_ext is not None:
        D_ext = hurst_to_dimension(H_ext)
    elif D_ext is None:
        raise ValueError("Must provide either D_ext or H_ext")
    
    H_ext = dimension_to_hurst(D_ext)
    H_int = dimension_to_hurst(D_int)
    
    # Calculate metrics
    R = resonance_index(D_ext, D_int)
    P_rec = pareidolia_probability(D_ext)
    beta_ext = spectral_exponent(H_ext)
    beta_int = spectral_exponent(H_int)
    entropy_rel = coding_entropy_relative(H_ext)
    
    # Distance from attractor
    delta_D = D_ext - D_ATTRACTOR
    delta_H = H_ext - H_ATTRACTOR
    
    results = {
        'D_ext': D_ext,
        'H_ext': H_ext,
        'D_int': D_int,
        'H_int': H_int,
        'D_attractor': D_ATTRACTOR,
        'H_attractor': H_ATTRACTOR,
        'resonance_index': R,
        'pareidolia_probability': P_rec,
        'spectral_beta_ext': beta_ext,
        'spectral_beta_int': beta_int,
        'coding_entropy_relative': entropy_rel,
        'delta_D_from_attractor': delta_D,
        'delta_H_from_attractor': delta_H,
    }
    
    if verbose:
        print_analysis(results)
    
    return results


def print_analysis(results):
    """Print formatted analysis results."""
    print("\n" + "="*60)
    print("  UNIVERSAL FRACTAL ATTRACTOR — RESONANCE ANALYSIS")
    print("="*60)
    
    print("\n📊 INPUT PARAMETERS:")
    print(f"   D_ext (stimulus):     {results['D_ext']:.4f}")
    print(f"   H_ext (stimulus):     {results['H_ext']:.4f}")
    print(f"   D_int (neural):       {results['D_int']:.4f}")
    print(f"   H_int (neural):       {results['H_int']:.4f}")
    
    print("\n🎯 ATTRACTOR REFERENCE:")
    print(f"   D* (attractor):       {results['D_attractor']:.4f}")
    print(f"   H* (attractor):       {results['H_attractor']:.4f}")
    print(f"   ΔD from attractor:    {results['delta_D_from_attractor']:+.4f}")
    print(f"   ΔH from attractor:    {results['delta_H_from_attractor']:+.4f}")
    
    print("\n🔮 RESONANCE METRICS:")
    R = results['resonance_index']
    P = results['pareidolia_probability']
    
    # Color-code resonance (using text indicators)
    if R > 0.95:
        r_indicator = "🟢 STRONG"
    elif R > 0.90:
        r_indicator = "🟡 MODERATE"
    else:
        r_indicator = "🔴 WEAK"
    
    print(f"   Resonance Index:      {R:.4f}  {r_indicator}")
    print(f"   Pareidolia Prob.:     {P:.4f}  ({P*100:.1f}%)")
    
    print("\n📈 SPECTRAL PROPERTIES:")
    print(f"   β_ext (S~f^-β):       {results['spectral_beta_ext']:.4f}")
    print(f"   β_int (neural):       {results['spectral_beta_int']:.4f}")
    print(f"   Coding entropy (rel): {results['coding_entropy_relative']:.6f}")
    
    print("\n📝 INTERPRETATION:")
    if R > 0.95:
        print("   Strong resonance: High pareidolia probability expected.")
        print("   Stimulus complexity matches neural processing optimally.")
    elif R > 0.90:
        print("   Moderate resonance: Pareidolia possible under attention.")
        print("   Slight mismatch between stimulus and neural complexity.")
    else:
        print("   Weak resonance: Pareidolia unlikely.")
        print("   Significant complexity mismatch.")
    
    print("\n" + "="*60 + "\n")


def batch_analysis(D_values, D_int=D_NEURAL):
    """
    Analyze multiple D values and return summary table.
    """
    results = []
    for D in D_values:
        r = full_analysis(D_ext=D, D_int=D_int, verbose=False)
        results.append(r)
    
    print("\n" + "="*70)
    print("  BATCH RESONANCE ANALYSIS")
    print("="*70)
    print(f"\n{'D_ext':>8} {'H_ext':>8} {'R':>8} {'P_rec':>8} {'Status':>12}")
    print("-"*50)
    
    for r in results:
        status = "STRONG" if r['resonance_index'] > 0.95 else \
                 "MODERATE" if r['resonance_index'] > 0.90 else "WEAK"
        print(f"{r['D_ext']:>8.3f} {r['H_ext']:>8.3f} "
              f"{r['resonance_index']:>8.4f} {r['pareidolia_probability']:>8.4f} "
              f"{status:>12}")
    
    return results


# =============================================================================
# Image Analysis (if available)
# =============================================================================

def analyze_image(image_path, D_int=D_NEURAL):
    """
    Analyze an image file and compute resonance metrics.
    
    Requires: opencv-python, numpy
    """
    try:
        import cv2
    except ImportError:
        print("Error: opencv-python required for image analysis")
        print("Install with: pip install opencv-python")
        return None
    
    # Load and preprocess
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"Error: Cannot load image {image_path}")
        return None
    
    # Binarize
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Simple box-counting (basic implementation)
    D_ext = simple_boxcount(binary)
    
    print(f"\n📷 IMAGE ANALYSIS: {image_path}")
    return full_analysis(D_ext=D_ext, D_int=D_int, verbose=True)


def simple_boxcount(binary, n_sizes=8):
    """
    Simple box-counting fractal dimension estimate.
    """
    import numpy as np
    
    arr = (binary > 0).astype(np.uint8)
    h, w = arr.shape
    max_size = min(h, w) // 2
    
    sizes = np.unique(np.logspace(np.log2(4), np.log2(max_size), 
                                  n_sizes, base=2).astype(int))
    
    counts = []
    for size in sizes:
        n_x = int(np.ceil(w / size))
        n_y = int(np.ceil(h / size))
        count = 0
        for i in range(n_y):
            for j in range(n_x):
                block = arr[i*size:(i+1)*size, j*size:(j+1)*size]
                if np.any(block):
                    count += 1
        counts.append(count)
    
    counts = np.array(counts)
    mask = counts > 0
    
    if mask.sum() < 2:
        return np.nan
    
    coeffs = np.polyfit(np.log(sizes[mask]), np.log(counts[mask]), 1)
    return -coeffs[0]


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LRD v6.3 — Resonance Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python resonance_calculator.py --D_ext 1.25
  python resonance_calculator.py --H_ext 0.72
  python resonance_calculator.py --D_ext 1.28 --D_int 1.40
  python resonance_calculator.py --batch 1.10,1.20,1.30,1.40,1.50
  python resonance_calculator.py --image rock_photo.png

Universal Fractal Attractor: D* ≈ 1.30, H* ≈ 0.70
Neural baseline: D_int ≈ 1.35, H_int ≈ 0.65
        """
    )
    
    parser.add_argument('--D_ext', type=float, help="External fractal dimension")
    parser.add_argument('--H_ext', type=float, help="External Hurst exponent")
    parser.add_argument('--D_int', type=float, default=D_NEURAL,
                       help=f"Internal (neural) fractal dimension (default: {D_NEURAL})")
    parser.add_argument('--batch', type=str, 
                       help="Comma-separated D values for batch analysis")
    parser.add_argument('--image', type=str, help="Image file to analyze")
    
    args = parser.parse_args()
    
    if args.image:
        analyze_image(args.image, D_int=args.D_int)
    elif args.batch:
        D_values = [float(x) for x in args.batch.split(',')]
        batch_analysis(D_values, D_int=args.D_int)
    elif args.D_ext is not None or args.H_ext is not None:
        full_analysis(D_ext=args.D_ext, H_ext=args.H_ext, D_int=args.D_int)
    else:
        # Demo mode
        print("\n🔬 DEMO MODE — Running example analysis\n")
        
        print("Example 1: Pareidolia-inducing rock (D = 1.25)")
        full_analysis(D_ext=1.25)
        
        print("\nExample 2: Control rock (D = 1.40)")
        full_analysis(D_ext=1.40)
        
        print("\nExample 3: Batch analysis")
        batch_analysis([1.10, 1.20, 1.25, 1.30, 1.35, 1.40, 1.50])


if __name__ == "__main__":
    main()
