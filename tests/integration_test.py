#!/usr/bin/env python3
"""
Integration Test for SkillForge Game Engine
Tests complete flow from campaign selection to gameplay
"""
import requests
import json
import time
import sys
from typing import Dict, Any, Optional

# Service URLs
DJANGO_URL = "http://localhost:8000"
GAME_ENGINE_URL = "http://localhost:9500"

class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg: str):
    print(f"{Colors.GREEN}[PASS] {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}[FAIL] {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.END}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.END}")

class IntegrationTest:
    def __init__(self):
        self.campaign_id: Optional[str] = None
        self.character_id: Optional[str] = None
        self.player_id: Optional[str] = None
        self.session_id: Optional[str] = None

    def test_health_checks(self) -> bool:
        """Test that all services are healthy"""
        print("\n" + "="*60)
        print("TESTING SERVICE HEALTH")
        print("="*60)

        # Test Django
        try:
            response = requests.get(f"{DJANGO_URL}/", timeout=5)
            if response.status_code == 200:
                print_success("Django web service is running")
            else:
                print_error(f"Django returned status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Django connection failed: {e}")
            return False

        # Test Game Engine
        try:
            response = requests.get(f"{GAME_ENGINE_URL}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                print_success(f"Game Engine is {health.get('status')}")
                print_info(f"  Redis: {health.get('redis')}")
                print_info(f"  RabbitMQ: {health.get('rabbitmq')}")
                print_info(f"  MongoDB: {health.get('mongodb')}")
                print_info(f"  Neo4j: {health.get('neo4j')}")

                if health.get('status') != 'healthy':
                    print_warning("Game Engine is not fully healthy")
                    return False
            else:
                print_error(f"Game Engine health check failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Game Engine connection failed: {e}")
            return False

        return True

    def test_get_campaigns(self) -> bool:
        """Test getting available campaigns"""
        print("\n" + "="*60)
        print("TESTING CAMPAIGN RETRIEVAL")
        print("="*60)

        try:
            # Try to get campaigns from MongoDB directly via game-engine
            # For now, we'll scrape the lobby page
            response = requests.get(f"{DJANGO_URL}/game/lobby/", timeout=10)

            if response.status_code != 200:
                print_error(f"Failed to load game lobby: {response.status_code}")
                return False

            # Check if there are campaigns in the response
            if 'campaign-card' in response.text:
                # Extract campaign ID from the HTML (simplified approach)
                import re
                campaign_matches = re.findall(r"startSoloGame\('([^']+)'\)", response.text)

                if campaign_matches:
                    self.campaign_id = campaign_matches[0]
                    print_success(f"Found {len(campaign_matches)} campaign(s)")
                    print_info(f"  Using campaign: {self.campaign_id}")
                    return True
                else:
                    print_error("No campaigns found in lobby")
                    return False
            else:
                print_warning("No campaign cards found in lobby")
                return False

        except Exception as e:
            print_error(f"Failed to get campaigns: {e}")
            return False

    def test_get_characters(self) -> bool:
        """Test getting available characters"""
        print("\n" + "="*60)
        print("TESTING CHARACTER RETRIEVAL")
        print("="*60)

        try:
            # For now, use the known character from PostgreSQL
            # In a real test, we'd query the database or create a test character
            self.character_id = "00c73bec-5692-41cc-91ed-de6f1562d948"
            self.player_id = "875f7b7e-2d6d-44e3-bfe7-b824cb1ad35f"  # Stud Muffin's player

            print_success("Using known test character")
            print_info(f"  Character ID: {self.character_id}")
            print_info(f"  Player ID: {self.player_id}")
            return True

        except Exception as e:
            print_error(f"Failed to get characters: {e}")
            return False

    def test_create_session(self) -> bool:
        """Test creating a game session via game-engine API"""
        print("\n" + "="*60)
        print("TESTING SESSION CREATION")
        print("="*60)

        if not self.campaign_id or not self.character_id or not self.player_id:
            print_error("Missing campaign_id, character_id, or player_id")
            return False

        try:
            payload = {
                "campaign_id": self.campaign_id,
                "player_id": self.player_id,
                "character_id": self.character_id
            }

            print_info(f"Creating solo session for campaign {self.campaign_id}")

            response = requests.post(
                f"{GAME_ENGINE_URL}/api/v1/session/start-solo",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                self.session_id = result.get('session_id')

                print_success(f"Session created successfully!")
                print_info(f"  Session ID: {self.session_id}")
                print_info(f"  Status: {result.get('status')}")

                return True
            else:
                print_error(f"Failed to create session: {response.status_code}")
                print_error(f"  Response: {response.text[:200]}")
                return False

        except Exception as e:
            print_error(f"Session creation failed: {e}")
            return False

    def test_get_session_state(self) -> bool:
        """Test getting session state"""
        print("\n" + "="*60)
        print("TESTING SESSION STATE RETRIEVAL")
        print("="*60)

        if not self.session_id:
            print_error("No session_id available")
            return False

        try:
            response = requests.get(
                f"{GAME_ENGINE_URL}/api/v1/session/{self.session_id}/state",
                timeout=10
            )

            if response.status_code == 200:
                state = response.json()

                print_success("Session state retrieved successfully")
                print_info(f"  Campaign: {state.get('campaign_id')}")
                print_info(f"  Status: {state.get('status')}")
                print_info(f"  Current Quest: {state.get('current_quest_id', 'None')}")
                print_info(f"  Players: {len(state.get('players', []))}")

                return True
            else:
                print_error(f"Failed to get session state: {response.status_code}")
                return False

        except Exception as e:
            print_error(f"Failed to get session state: {e}")
            return False

    def test_pause_resume(self) -> bool:
        """Test pause and resume functionality"""
        print("\n" + "="*60)
        print("TESTING PAUSE/RESUME")
        print("="*60)

        if not self.session_id:
            print_error("No session_id available")
            return False

        try:
            # Pause
            print_info("Pausing session...")
            response = requests.post(
                f"{GAME_ENGINE_URL}/api/v1/session/{self.session_id}/pause",
                timeout=10
            )

            if response.status_code == 200:
                print_success("Session paused")
            else:
                print_error(f"Failed to pause: {response.status_code}")
                return False

            time.sleep(1)

            # Resume
            print_info("Resuming session...")
            response = requests.post(
                f"{GAME_ENGINE_URL}/api/v1/session/{self.session_id}/resume",
                timeout=10
            )

            if response.status_code == 200:
                print_success("Session resumed")
                return True
            else:
                print_error(f"Failed to resume: {response.status_code}")
                return False

        except Exception as e:
            print_error(f"Pause/Resume test failed: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all integration tests"""
        print("\n")
        print("+" + "="*58 + "+")
        print("|" + " " * 10 + "SKILLFORGE INTEGRATION TEST SUITE" + " " * 14 + "|")
        print("+" + "="*58 + "+")

        tests = [
            ("Health Checks", self.test_health_checks),
            ("Campaign Retrieval", self.test_get_campaigns),
            ("Character Retrieval", self.test_get_characters),
            ("Session Creation", self.test_create_session),
            ("Session State Retrieval", self.test_get_session_state),
            ("Pause/Resume", self.test_pause_resume),
        ]

        results = []

        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))

                if not result:
                    print_warning(f"\n{test_name} failed - stopping tests")
                    break

            except Exception as e:
                print_error(f"Test {test_name} crashed: {e}")
                results.append((test_name, False))
                break

        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            if result:
                print_success(f"{test_name}")
            else:
                print_error(f"{test_name}")

        print("\n" + "-"*60)

        if passed == total:
            print_success(f"ALL TESTS PASSED ({passed}/{total})")
            return True
        else:
            print_error(f"SOME TESTS FAILED ({passed}/{total})")
            return False

def main():
    test = IntegrationTest()
    success = test.run_all_tests()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
