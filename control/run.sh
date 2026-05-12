# Print out the value of DEVELOPMENT
echo "================================================"
echo "DEVELOPMENT is set to: $DEVELOPMENT"
echo "================================================"

# If development is true, run with dev_runner.py, otherwise run with main.py
if [ "$DEVELOPMENT" = "true" ]; then
    echo "Running in development mode (hotreloading main.py)"
    python dev_runner.py
else
    echo "Running main.py"
    python main.py
fi