#!/usr/bin/env python3
"""
surrogate_tests.py
==================
LRD v6.2 — Surrogate Analysis for Pareidolia Images

Statistical tests using phase-randomized and block-shuffled surrogates
to verify that fractal signatures are genuine structural properties.

Part of LRD v6.2: Fractal Synergy in Perception
Author: Igor Chechelnitsky (ORCID: 0009-0007-4607-1946)
License: CC BY 4.0

Usage:
    python surrogate_tests.py --input results/metrics.csv --images images/ --output surrogates/
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import cv2
from glob import glob

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(x, **kwargs):
        return x


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def load_gray(path, max_side=1200):
    """Load image as grayscale."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise IOError(f"Cannot read image: {path}")
    h, w = img.shape
    if max(h, w) > max_side:
        scale = max_side / float(max(h, w))
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return img


# =============================================================================
# Surrogate Generation
# =============================================================================

def phase_randomize(gray):
    """
    Phase-randomized surrogate: preserves power spectrum, destroys structure.
    """
    f = np.fft.fft2(gray.astype(float))
    magnitude = np.abs(f)
    
    # Random phases
    random_phase = np.random.uniform(-np.pi, np.pi, f.shape)
    
    new_f = magnitude * np.exp(1j * random_phase)
    surrogate = np.real(np.fft.ifft2(new_f))
    
    # Rescale
    surrogate = ((surrogate - surrogate.min()) / 
                 (surrogate.max() - surrogate.min() + 1e-10) * 255)
    return surrogate.astype(np.uint8)


def block_shuffle(gray, block_size=16):
    """
    Block-shuffled surrogate: randomly permutes blocks.
    """
    h, w = gray.shape
    n_blocks_h = h // block_size
    n_blocks_w = w // block_size
    
    # Extract blocks
    blocks = []
    for i in range(n_blocks_h):
        for j in range(n_blocks_w):
            block = gray[i*block_size:(i+1)*block_size, 
                        j*block_size:(j+1)*block_size]
            blocks.append(block.copy())
    
    # Shuffle
    np.random.shuffle(blocks)
    
    # Reconstruct
    result = np.zeros_like(gray)
    idx = 0
    for i in range(n_blocks_h):
        for j in range(n_blocks_w):
            result[i*block_size:(i+1)*block_size,
                  j*block_size:(j+1)*block_size] = blocks[idx]
            idx += 1
    
    return result


# =============================================================================
# Fractal Dimension (simplified)
# =============================================================================

def boxcount_fd(binary, min_size=4, n_sizes=10):
    """Quick box-counting FD estimate."""
    arr = (binary > 0).astype(np.uint8)
    h, w = arr.shape
    max_size = min(h, w) // 2
    
    sizes = np.unique(np.logspace(np.log2(min_size), np.log2(max_size),
                                  num=n_sizes, base=2).astype(int))
    sizes = sizes[sizes > 0]
    
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


def symmetry_score(gray):
    """Horizontal mirror correlation."""
    flipped = np.fliplr(gray)
    g1 = gray.astype(float) - np.mean(gray)
    g2 = flipped.astype(float) - np.mean(flipped)
    return np.sum(g1 * g2) / (np.sqrt(np.sum(g1**2)) * np.sqrt(np.sum(g2**2)) + 1e-10)


# =============================================================================
# Surrogate Test
# =============================================================================

def run_surrogate_test(gray, n_surrogates=99):
    """
    Run surrogate test for FD and symmetry.
    
    Returns dict with original values and percentiles.
    """
    # Binarize
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Original metrics
    fd_orig = boxcount_fd(binary)
    sym_orig = symmetry_score(gray)
    
    # Surrogates
    fd_phase = []
    fd_block = []
    sym_phase = []
    sym_block = []
    
    for _ in range(n_surrogates):
        # Phase-randomized
        surr_p = phase_randomize(gray)
        _, bin_p = cv2.threshold(surr_p, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        fd_phase.append(boxcount_fd(bin_p))
        sym_phase.append(symmetry_score(surr_p))
        
        # Block-shuffled
        surr_b = block_shuffle(gray, block_size=16)
        _, bin_b = cv2.threshold(surr_b, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        fd_block.append(boxcount_fd(bin_b))
        sym_block.append(symmetry_score(surr_b))
    
    fd_phase = np.array([x for x in fd_phase if not np.isnan(x)])
    fd_block = np.array([x for x in fd_block if not np.isnan(x)])
    sym_phase = np.array(sym_phase)
    sym_block = np.array(sym_block)
    
    # Percentiles
    fd_pctl_phase = np.mean(fd_phase >= fd_orig) if len(fd_phase) > 0 else np.nan
    fd_pctl_block = np.mean(fd_block >= fd_orig) if len(fd_block) > 0 else np.nan
    sym_pctl_phase = np.mean(sym_phase <= sym_orig)
    sym_pctl_block = np.mean(sym_block <= sym_orig)
    
    return {
        'fd_original': fd_orig,
        'fd_phase_mean': np.mean(fd_phase) if len(fd_phase) > 0 else np.nan,
        'fd_phase_std': np.std(fd_phase) if len(fd_phase) > 0 else np.nan,
        'fd_phase_pctl': fd_pctl_phase,
        'fd_block_mean': np.mean(fd_block) if len(fd_block) > 0 else np.nan,
        'fd_block_std': np.std(fd_block) if len(fd_block) > 0 else np.nan,
        'fd_block_pctl': fd_pctl_block,
        'sym_original': sym_orig,
        'sym_phase_mean': np.mean(sym_phase),
        'sym_phase_std': np.std(sym_phase),
        'sym_phase_pctl': sym_pctl_phase,
        'sym_block_mean': np.mean(sym_block),
        'sym_block_std': np.std(sym_block),
        'sym_block_pctl': sym_pctl_block
    }


def main(args):
    ensure_dir(args.output)
    
    # Find images
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
    files = []
    for ext in extensions:
        files.extend(glob(os.path.join(args.images, ext)))
        files.extend(glob(os.path.join(args.images, ext.upper())))
    files = sorted(set(files))
    
    if len(files) == 0:
        print(f"No images found in {args.images}")
        sys.exit(1)
    
    print(f"Running surrogate tests on {len(files)} images...")
    
    results = []
    iterator = tqdm(files, desc="Testing") if HAS_TQDM else files
    
    for path in iterator:
        try:
            gray = load_gray(path, max_side=args.resize)
            res = run_surrogate_test(gray, n_surrogates=args.n_surrogates)
            res['filename'] = os.path.basename(path)
            results.append(res)
        except Exception as e:
            print(f"Error with {path}: {e}")
    
    # Save results
    df = pd.DataFrame(results)
    csv_path = os.path.join(args.output, "surrogate_results.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"\nResults saved to {csv_path}")
    
    # Summary
    if len(results) > 0:
        sig_fd = (df['fd_phase_pctl'] < 0.05).sum()
        sig_sym = (df['sym_phase_pctl'] > 0.95).sum()
        print(f"\nSignificant FD differences (p<0.05): {sig_fd}/{len(results)}")
        print(f"Significant symmetry differences (p>0.95): {sig_sym}/{len(results)}")
        
        # Plot if matplotlib available
        if HAS_MATPLOTLIB:
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            
            # FD histogram
            axes[0].hist(df['fd_phase_pctl'].dropna(), bins=20, 
                        color='#2563eb', alpha=0.7, edgecolor='white')
            axes[0].axvline(0.05, color='red', linestyle='--', 
                           label='α=0.05')
            axes[0].set_xlabel('Percentile (FD vs Phase-Surrogates)')
            axes[0].set_ylabel('Count')
            axes[0].set_title('Fractal Dimension Surrogate Test')
            axes[0].legend()
            
            # Symmetry histogram
            axes[1].hist(df['sym_phase_pctl'].dropna(), bins=20,
                        color='#16a34a', alpha=0.7, edgecolor='white')
            axes[1].axvline(0.95, color='red', linestyle='--',
                           label='α=0.05')
            axes[1].set_xlabel('Percentile (Symmetry vs Phase-Surrogates)')
            axes[1].set_ylabel('Count')
            axes[1].set_title('Symmetry Surrogate Test')
            axes[1].legend()
            
            fig.tight_layout()
            fig.savefig(os.path.join(args.output, 'surrogate_summary.png'), 
                       dpi=150)
            plt.close()
            print(f"Summary plot saved to {args.output}/surrogate_summary.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LRD v6.2 — Surrogate Tests for Pareidolia Images"
    )
    parser.add_argument('--images', type=str, required=True,
                       help="Folder with images to test")
    parser.add_argument('--output', type=str, required=True,
                       help="Output folder for results")
    parser.add_argument('--n_surrogates', type=int, default=99,
                       help="Number of surrogates per image (default: 99)")
    parser.add_argument('--resize', type=int, default=800,
                       help="Max image side (default: 800)")
    
    args = parser.parse_args()
    main(args)
