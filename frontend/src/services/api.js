import axios from "axios";

// Read API URL from .env
const API_URL = process.env.REACT_APP_API_URL;

export const fetchRecs = async (userId) => {
  try {
    const response = await axios.post(`${API_URL}/recommend/`, { user_id: userId });
    return response.data;
  } catch (error) {
    console.error("Error fetching recommendations:", error);
    throw error;
  }
};
