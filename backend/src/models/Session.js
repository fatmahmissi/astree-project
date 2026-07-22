const mongoose = require('mongoose');

/**
 * Une Session represente une conversation entre un utilisateur et le chatbot.
 * Elle regroupe plusieurs Messages (question + reponse).
 */
const sessionSchema = new mongoose.Schema(
  {
    sessionId: {
      type: String,
      required: true,
      unique: true,
      index: true,
    },
    dateCreation: {
      type: Date,
      default: Date.now,
    },
    derniereActivite: {
      type: Date,
      default: Date.now,
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Session', sessionSchema);
