#!/usr/bin/env python3
"""Test runner script for SensorThings integration."""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"❌ {description} failed with return code {result.returncode}")
        return False
    else:
        print(f"✅ {description} completed successfully")
        return True


def main():
    """Main test runner."""
    print("🧪 SensorThings Integration Test Suite")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("sensorthings").exists():
        print("❌ Error: sensorthings directory not found. Please run from project root.")
        sys.exit(1)
    
    # Install test requirements
    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"], 
                      "Installing test requirements"):
        sys.exit(1)
    
    # Run linting
    if not run_command([sys.executable, "-m", "flake8", "sensorthings/", "--max-line-length=88"], 
                      "Running flake8 linting"):
        print("⚠️  Linting issues found, but continuing with tests...")
    
    # Run type checking
    if not run_command([sys.executable, "-m", "mypy", "sensorthings/", "--ignore-missing-imports"], 
                      "Running mypy type checking"):
        print("⚠️  Type checking issues found, but continuing with tests...")
    
    # Run unit tests
    if not run_command([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"], 
                      "Running unit tests"):
        sys.exit(1)
    
    # Run tests with coverage
    if not run_command([sys.executable, "-m", "pytest", "tests/", "--cov=sensorthings", 
                       "--cov-report=term-missing", "--cov-report=html"], 
                      "Running tests with coverage"):
        sys.exit(1)
    
    # Run integration tests specifically
    if not run_command([sys.executable, "-m", "pytest", "tests/components/sensorthings/test_integration.py", "-v"], 
                      "Running integration tests"):
        sys.exit(1)
    
    print("\n🎉 All tests completed successfully!")
    print("📊 Coverage report generated in htmlcov/index.html")
    print("📋 Check the output above for any warnings or issues.")


if __name__ == "__main__":
    main()
