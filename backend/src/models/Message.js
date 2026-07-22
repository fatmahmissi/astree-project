const mongoose = require('mongoose');

/**
 * Un Message represente un echange question/reponse dans une Session.
 */
const sourceSchema = new mongoose.Schema(
  {
    url: String,
    pageTitre: String,
    distance: Number,
  },
  { _id: false }
);

const messageSchema = new mongoose.Schema(
  {
    sessionId: {
      type: String,
      required: true,
      index: true,
    },
    question: {
      type: String,
      required: true,
    },
    reponse: {
      type: String,
      required: true,
    },
    sources: [sourceSchema],
    nbChunks: {
      type: Number,
      default: 0,
    },
    dureeMs: {
      type: Number,
      default: 0,
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Message', messageSchema);
