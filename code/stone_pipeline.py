#!/usr/bin/env python3
"""
stone_pipeline.py
=================
LRD v6.2 — Pareidolia Image Analysis Pipeline

Batch image processing for fractal analysis of rock formations:
- Preprocessing (resize, grayscale, binarization)
- Box-counting fractal dimension with bootstrap CI
- Spectral fractal analysis
- Edge density, texture entropy, symmetry, saliency metrics
- Surrogate tests (phase-randomization)
- CSV output with full metrics

Part of LRD v6.2: Fractal Synergy in Perception
Author: Igor Chechelnitsky (ORCID: 0009-0007-4607-1946)
License: CC BY 4.0

Usage:
    python stone_pipeline.py --input images/ --output results/ --method otsu --resize 1200

References:
    - LRD v6.0.1: https://doi.org/10.5281/zenodo.18018292
    - Taylor et al. (2017) Nature Sci. Rep. 7: 42375
"""

import os
import sys
import argparse
import math
import numpy as np
import cv2
from glob import glob
import pandas as pd

# Optional imports with fallbacks
try:
    from skimage import metrics as skmetrics
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False
    print("Warning: scikit-image not found. SSIM will be disabled.")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(x, **kwargs):
        return x

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not found. Plots will be disabled.")


# =============================================================================
# Utility Functions
# =============================================================================

def ensure_dir(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def load_and_resize(path, max_side=1200):
    """Load image and resize if larger than max_side."""
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"Cannot read image: {path}")
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > max_side:
        scale = max_side / float(max(h, w))
        img = cv2.resize(img, (int(w * scale), int(h * scale)), 
                        interpolation=cv2.INTER_AREA)
    return img, scale


def to_gray(img):
    """Convert BGR to grayscale."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# =============================================================================
# Preprocessing
# =============================================================================

def binarize(image_gray, method='otsu', block_size=51, c=2):
    """
    Binarize grayscale image.
    
    Parameters:
        method: 'otsu' or 'adaptive'
        block_size: for adaptive thresholding
        c: constant subtracted from mean (adaptive)
    """
    if method == 'otsu':
        _, th = cv2.threshold(image_gray, 0, 255, 
                             cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return th
    else:  # adaptive
        th = cv2.adaptiveThreshold(image_gray, 255, 
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, block_size, c)
        return th


def morph_clean(binary, kernel_size=3):
    """Morphological cleaning (open + close)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                       (kernel_size, kernel_size))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=1)
    return closed


def edge_image(gray):
    """Extract edges using Canny detector."""
    return cv2.Canny(gray, 50, 150)


# =============================================================================
# Fractal Dimension (Box-Counting)
# =============================================================================

def boxcount(binary, sizes):
    """
    Count boxes needed to cover the binary image at each scale.
    
    Parameters:
        binary: uint8 array (0 or 255)
        sizes: array of box sizes
    
    Returns:
        counts: array of box counts for each size
    """
    h, w = binary.shape
    counts = []
    for size in sizes:
        if size <= 0:
            counts.append(np.nan)
            continue
        n_box_x = int(math.ceil(w / size))
        n_box_y = int(math.ceil(h / size))
        count = 0
        for i in range(n_box_y):
            for j in range(n_box_x):
                y0, x0 = i * size, j * size
                block = binary[y0:y0+size, x0:x0+size]
                if np.any(block):
                    count += 1
        counts.append(count)
    return np.array(counts)


def fractal_dimension_boxcount(binary, min_size=4, max_size=None, n_sizes=10):
    """
    Compute box-counting fractal dimension.
    
    Parameters:
        binary: binarized image (uint8, 0/255)
        min_size: minimum box size
        max_size: maximum box size (default: min dimension / 2)
        n_sizes: number of logarithmically-spaced sizes
    
    Returns:
        D: fractal dimension
        sizes: box sizes used
        counts: box counts at each size
    """
    arr = (binary > 0).astype(np.uint8)
    h, w = arr.shape
    if max_size is None:
        max_size = min(h, w) // 2
    
    # Logarithmically-spaced box sizes
    sizes = np.unique(np.logspace(np.log2(min_size), np.log2(max_size), 
                                  num=n_sizes, base=2).astype(int))
    sizes = sizes[sizes > 0]
    
    counts = boxcount(arr, sizes)
    
    # Linear regression in log-log space
    mask = (counts > 0) & (~np.isnan(counts))
    if mask.sum() < 2:
        return np.nan, sizes, counts
    
    coeffs = np.polyfit(np.log(sizes[mask]), np.log(counts[mask]), 1)
    D = -coeffs[0]  # Negative slope = fractal dimension
    
    return float(D), sizes, counts


def bootstrap_fd(binary, n_iter=50, min_size=4, max_size=None, n_sizes=10):
    """
    Bootstrap estimate of fractal dimension with uncertainty.
    
    Uses random 80-100% area crops to assess sensitivity.
    """
    vals = []
    h, w = binary.shape
    
    for _ in range(n_iter):
        # Random crop (80-100% of area)
        frac = np.random.uniform(0.8, 1.0)
        new_h, new_w = int(h * frac), int(w * frac)
        y0 = np.random.randint(0, max(1, h - new_h + 1))
        x0 = np.random.randint(0, max(1, w - new_w + 1))
        crop = binary[y0:y0+new_h, x0:x0+new_w]
        
        D, _, _ = fractal_dimension_boxcount(crop, min_size, max_size, n_sizes)
        if not np.isnan(D):
            vals.append(D)
    
    if len(vals) == 0:
        return np.nan, np.array([])
    
    return float(np.mean(vals)), np.array(vals)


# =============================================================================
# Spectral Fractal Analysis
# =============================================================================

def spectral_fractal_index(gray):
    """
    Compute spectral fractal index from 2D FFT.
    
    Returns the negative slope of log(power) vs log(frequency).
    """
    f = np.fft.fft2(gray.astype(float))
    f_shift = np.fft.fftshift(f)
    magnitude = np.abs(f_shift)
    
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    
    # Radial averaging
    max_r = min(cy, cx)
    radii = np.arange(1, max_r)
    power = []
    
    for r in radii:
        mask = np.zeros((h, w), dtype=bool)
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((y - cy)**2 + (x - cx)**2)
        mask = (dist >= r - 0.5) & (dist < r + 0.5)
        if mask.sum() > 0:
            power.append(np.mean(magnitude[mask]))
        else:
            power.append(np.nan)
    
    power = np.array(power)
    valid = ~np.isnan(power) & (power > 0)
    
    if valid.sum() < 3:
        return np.nan
    
    # Fit in log-log space
    log_r = np.log(radii[valid])
    log_p = np.log(power[valid])
    coeffs = np.polyfit(log_r, log_p, 1)
    
    return -coeffs[0]  # Beta exponent


# =============================================================================
# Additional Metrics
# =============================================================================

def edge_density(gray):
    """Fraction of edge pixels (Canny edges / total area)."""
    edges = cv2.Canny(gray, 50, 150)
    return np.sum(edges > 0) / edges.size


def texture_entropy(gray):
    """Shannon entropy of grayscale histogram."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    hist = hist[hist > 0]
    p = hist / hist.sum()
    return -np.sum(p * np.log2(p))


def symmetry_score(gray):
    """Horizontal symmetry (correlation with mirror image)."""
    flipped = np.fliplr(gray)
    # Normalize for correlation
    g1 = gray.astype(float) - np.mean(gray)
    g2 = flipped.astype(float) - np.mean(flipped)
    
    corr = np.sum(g1 * g2) / (np.sqrt(np.sum(g1**2)) * np.sqrt(np.sum(g2**2)) + 1e-10)
    return float(corr)


def saliency_score(gray):
    """Mean gradient magnitude (Sobel filter)."""
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    return float(np.mean(mag) / 255.0)  # Normalize


# =============================================================================
# Surrogate Tests
# =============================================================================

def phase_randomize(gray):
    """
    Create phase-randomized surrogate.
    
    Preserves power spectrum, destroys spatial structure.
    """
    f = np.fft.fft2(gray.astype(float))
    magnitude = np.abs(f)
    phase = np.angle(f)
    
    # Random phase
    random_phase = np.random.uniform(-np.pi, np.pi, f.shape)
    
    # Preserve Hermitian symmetry for real output
    h, w = f.shape
    random_phase[:h//2, :] = -random_phase[h//2:, :][::-1, ::-1]
    
    new_f = magnitude * np.exp(1j * random_phase)
    surrogate = np.real(np.fft.ifft2(new_f))
    
    # Rescale to 0-255
    surrogate = ((surrogate - surrogate.min()) / 
                 (surrogate.max() - surrogate.min() + 1e-10) * 255).astype(np.uint8)
    
    return surrogate


def surrogate_test(gray, metric_func, n_surrogates=99):
    """
    Test if original metric differs from surrogate distribution.
    
    Returns:
        original: original metric value
        surr_mean: mean of surrogate distribution
        surr_std: std of surrogate distribution
        p_value: proportion of surrogates >= original (one-tailed)
    """
    original = metric_func(gray)
    
    surr_values = []
    for _ in range(n_surrogates):
        surr = phase_randomize(gray)
        surr_values.append(metric_func(surr))
    
    surr_values = np.array(surr_values)
    surr_mean = np.mean(surr_values)
    surr_std = np.std(surr_values)
    
    # One-tailed test (original < surrogates for FD)
    p_value = np.mean(surr_values <= original)
    
    return original, surr_mean, surr_std, p_value


# =============================================================================
# IFS Synthetic (for comparison)
# =============================================================================

def generate_ifs_pentagon(size=512, n_points=200000, r=0.618034):
    """
    Generate golden-ratio IFS fractal (pentagon attractor).
    
    For visual comparison / SSIM calculation.
    """
    center = np.array([size/2, size/2])
    
    # 5 fixed points on circle
    angles = np.deg2rad(np.arange(0, 360, 72))
    fixed = center + (size * 0.35) * np.column_stack([np.cos(angles), np.sin(angles)])
    
    arr = np.zeros((size, size), dtype=np.uint8)
    p = np.array([size * 0.1, size * 0.1])
    
    for _ in range(n_points):
        j = np.random.randint(0, 5)
        p = r * p + (1 - r) * fixed[j]
        xi = int(np.clip(p[0], 0, size - 1))
        yi = int(np.clip(p[1], 0, size - 1))
        arr[yi, xi] = min(255, arr[yi, xi] + 5)
    
    return arr


# =============================================================================
# Main Processing Pipeline
# =============================================================================

def process_image(path, outdir, args):
    """
    Process single image through full pipeline.
    
    Returns dict with all computed metrics.
    """
    name = os.path.splitext(os.path.basename(path))[0]
    
    # Load and preprocess
    img, scale = load_and_resize(path, max_side=args.resize)
    gray = to_gray(img)
    
    # Binarize and clean
    binary = binarize(gray, method=args.method, 
                     block_size=args.adaptive_block, c=args.adaptive_c)
    clean = morph_clean(binary, kernel_size=args.morph_kernel)
    edges = edge_image(gray)
    
    # Fractal dimension (single estimate)
    D_single, sizes, counts = fractal_dimension_boxcount(
        clean, min_size=args.min_box, max_size=None, n_sizes=args.n_sizes)
    
    # Bootstrap estimate
    D_mean, bootstrap_vals = bootstrap_fd(
        clean, n_iter=args.bootstrap, min_size=args.min_box, 
        max_size=None, n_sizes=args.n_sizes)
    
    # Spectral index
    spectral_idx = spectral_fractal_index(gray)
    
    # Additional metrics
    edge_dens = edge_density(gray)
    entropy = texture_entropy(gray)
    symmetry = symmetry_score(gray)
    saliency = saliency_score(gray)
    
    # SSIM with IFS (if available)
    ssim_val = np.nan
    if HAS_SKIMAGE:
        synth = generate_ifs_pentagon(size=min(gray.shape))
        synth_resized = cv2.resize(synth, (gray.shape[1], gray.shape[0]), 
                                   interpolation=cv2.INTER_AREA)
        try:
            ssim_val = skmetrics.structural_similarity(
                gray / 255.0, synth_resized / 255.0, data_range=1.0)
        except Exception:
            pass
    
    # Save outputs
    out_base = os.path.join(outdir, name)
    cv2.imwrite(out_base + "_gray.png", gray)
    cv2.imwrite(out_base + "_binary.png", clean)
    cv2.imwrite(out_base + "_edges.png", edges)
    
    # Box-count plot
    if HAS_MATPLOTLIB:
        fig, ax = plt.subplots(figsize=(5, 4))
        mask = (counts > 0) & (~np.isnan(counts))
        if mask.sum() >= 2:
            ax.plot(np.log(sizes[mask]), np.log(counts[mask]), 'o-', 
                   color='#2563eb', markersize=6, linewidth=2)
            if not np.isnan(D_single):
                slope = -D_single
                x = np.array([np.min(np.log(sizes[mask])), 
                             np.max(np.log(sizes[mask]))])
                intercept = np.polyfit(np.log(sizes[mask]), 
                                       np.log(counts[mask]), 1)[1]
                ax.plot(x, slope * x + intercept, '--', color='#dc2626',
                       linewidth=2, label=f"D = {D_single:.3f}")
                ax.legend(fontsize=10)
        ax.set_xlabel("log(box size)", fontsize=11)
        ax.set_ylabel("log(N)", fontsize=11)
        ax.set_title(f"Box-Counting: {name}", fontsize=12)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_base + "_boxcount_plot.png", dpi=150)
        plt.close(fig)
    
    # Compile results
    metrics = {
        'filename': os.path.basename(path),
        'scale': float(scale),
        'D_boxcount': float(D_single) if not np.isnan(D_single) else None,
        'D_bootstrap_mean': float(D_mean) if not np.isnan(D_mean) else None,
        'D_bootstrap_std': float(np.std(bootstrap_vals)) if len(bootstrap_vals) > 0 else None,
        'D_spectral': float(spectral_idx) if not np.isnan(spectral_idx) else None,
        'edge_density': float(edge_dens),
        'texture_entropy': float(entropy),
        'symmetry_score': float(symmetry),
        'saliency_score': float(saliency),
        'SSIM_ifs': float(ssim_val) if not np.isnan(ssim_val) else None
    }
    
    return metrics


def main(args):
    """Main entry point."""
    ensure_dir(args.output)
    
    # Find all image files
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tif', '*.tiff']
    files = []
    for ext in extensions:
        files.extend(glob(os.path.join(args.input, ext)))
        files.extend(glob(os.path.join(args.input, ext.upper())))
    files = sorted(set(files))
    
    if len(files) == 0:
        print(f"No image files found in {args.input}")
        sys.exit(1)
    
    print(f"Found {len(files)} images to process")
    
    # Process each image
    rows = []
    iterator = tqdm(files, desc="Processing") if HAS_TQDM else files
    
    for path in iterator:
        try:
            result = process_image(path, args.output, args)
            rows.append(result)
        except Exception as e:
            print(f"Error processing {path}: {e}")
    
    # Save results
    df = pd.DataFrame(rows)
    csv_path = os.path.join(args.output, "metrics.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"\nDone! Results saved to {csv_path}")
    print(f"Processed {len(rows)} images successfully")
    
    # Summary statistics
    if len(rows) > 0:
        print("\n--- Summary Statistics ---")
        print(f"D_boxcount:  mean={df['D_boxcount'].mean():.3f}, "
              f"std={df['D_boxcount'].std():.3f}")
        print(f"Symmetry:    mean={df['symmetry_score'].mean():.3f}, "
              f"std={df['symmetry_score'].std():.3f}")
        print(f"Saliency:    mean={df['saliency_score'].mean():.3f}, "
              f"std={df['saliency_score'].std():.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LRD v6.2 — Pareidolia Image Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python stone_pipeline.py --input images/ --output results/
  python stone_pipeline.py --input photos/ --output out/ --method adaptive --resize 800

References:
  LRD v6.0.1: https://doi.org/10.5281/zenodo.18018292
  GitHub: https://github.com/Muhomor2/LRD-v6.2-Pareidolia
        """
    )
    
    parser.add_argument('--input', type=str, required=True,
                       help="Input folder containing images")
    parser.add_argument('--output', type=str, required=True,
                       help="Output folder for results")
    parser.add_argument('--method', type=str, default='otsu',
                       choices=['otsu', 'adaptive'],
                       help="Binarization method (default: otsu)")
    parser.add_argument('--adaptive_block', type=int, default=51,
                       help="Block size for adaptive threshold (default: 51)")
    parser.add_argument('--adaptive_c', type=int, default=2,
                       help="Constant C for adaptive threshold (default: 2)")
    parser.add_argument('--morph_kernel', type=int, default=3,
                       help="Morphological kernel size (default: 3)")
    parser.add_argument('--min_box', type=int, default=4,
                       help="Minimum box size for box-counting (default: 4)")
    parser.add_argument('--n_sizes', type=int, default=10,
                       help="Number of box sizes (default: 10)")
    parser.add_argument('--bootstrap', type=int, default=50,
                       help="Bootstrap iterations (default: 50)")
    parser.add_argument('--resize', type=int, default=1200,
                       help="Max side length to resize images (default: 1200)")
    
    args = parser.parse_args()
    main(args)
